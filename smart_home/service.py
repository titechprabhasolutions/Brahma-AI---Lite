from __future__ import annotations

import importlib.util
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .providers.base import ProviderField, SmartHomeProvider
from .providers.builtin import built_in_provider_classes
from .storage import BASE_DIR, SmartHomeStorage


@dataclass(frozen=True)
class PlatformInfo:
    key: str
    name: str
    available: bool
    coming_soon: bool
    auth_fields: list[ProviderField]


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, type[SmartHomeProvider]] = {}
        self._load_builtins()
        self._load_external_plugins()

    def _load_builtins(self) -> None:
        for provider_cls in built_in_provider_classes():
            self._providers[provider_cls.key] = provider_cls

    def _load_external_plugins(self) -> None:
        plugins_dir = BASE_DIR / "smart_home" / "providers" / "plugins"
        if not plugins_dir.exists():
            return
        for path in plugins_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(f"smart_home_plugin_{path.stem}", path)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                register = getattr(module, "register", None)
                if callable(register):
                    for provider_cls in register() or []:
                        if isinstance(provider_cls, type) and issubclass(provider_cls, SmartHomeProvider):
                            self._providers[provider_cls.key] = provider_cls
            except Exception:
                continue

    def get(self, key: str) -> SmartHomeProvider:
        provider_cls = self._providers[key]
        return provider_cls()

    def platforms(self) -> list[PlatformInfo]:
        results = []
        for key, provider_cls in self._providers.items():
            provider = provider_cls()
            results.append(
                PlatformInfo(
                    key=key,
                    name=provider.name,
                    available=bool(provider.available),
                    coming_soon=bool(provider.coming_soon),
                    auth_fields=provider.auth_fields(),
                )
            )
        results.sort(key=lambda item: item.name.lower())
        return results


class SmartHomeService:
    def __init__(self, storage: SmartHomeStorage | None = None):
        self._storage = storage or SmartHomeStorage()
        self._registry = ProviderRegistry()

    def list_platforms(self) -> list[PlatformInfo]:
        return self._registry.platforms()

    def auth_fields_for(self, provider_key: str) -> list[ProviderField]:
        return self._registry.get(provider_key).auth_fields()

    def preview_discovery(self, provider_key: str, credentials: dict[str, Any]) -> dict[str, Any]:
        provider = self._registry.get(provider_key)
        auth = provider.authenticate(credentials)
        devices = provider.discover_devices(auth["credentials"])
        return {"account_label": auth["account_label"], "credentials": auth["credentials"], "devices": devices}

    def connect_devices(self, provider_key: str, account_label: str, credentials: dict[str, Any],
                        external_ids: list[str]) -> list[dict[str, Any]]:
        provider = self._registry.get(provider_key)
        auth = provider.authenticate(credentials)
        discovered = provider.discover_devices(auth["credentials"])
        selected = [device for device in discovered if str(device["external_id"]) in set(external_ids)]
        if not selected:
            return []
        account_id = self._storage.save_provider_account(provider_key, account_label or auth["account_label"], auth["credentials"])
        self._storage.save_devices(account_id, provider_key, selected)
        self._storage.log_activity(provider.name, f"Connected {len(selected)} device(s).")
        return self.list_devices()

    def list_devices(self, search: str = "", room: str = "") -> list[dict[str, Any]]:
        return self._storage.list_devices(search, room)

    def recent_activity(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._storage.recent_activity(limit)

    def device_count(self) -> int:
        return self._storage.count_devices()

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        return self._storage.get_device(device_id)

    def execute_device_action(self, device_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        device = self._storage.get_device(device_id)
        if not device:
            raise ValueError("Device not found.")
        provider = self._registry.get(device["provider_key"])
        account = self._storage.get_provider_account(device["provider_account_id"])
        runtime_device = dict(device)
        runtime_device["provider_credentials"] = (account or {}).get("credentials", {})
        result = provider.execute(runtime_device, action, payload)
        self._storage.update_device(device_id, is_on=result.get("is_on"), traits=result.get("traits"))
        self._storage.log_activity(device["name"], str(result.get("detail", "Device updated.")))
        updated = self._storage.get_device(device_id)
        return {"device": updated, "detail": result.get("detail", "Device updated.")}

    def rename_device(self, device_id: str, new_name: str) -> None:
        device = self._storage.get_device(device_id)
        if not device:
            raise ValueError("Device not found.")
        self._storage.update_device(device_id, name=new_name.strip() or device["name"])
        self._storage.log_activity(device["name"], f"Renamed to {new_name.strip() or device['name']}.")

    def forget_device(self, device_id: str) -> None:
        device = self._storage.get_device(device_id)
        if not device:
            return
        self._storage.forget_device(device_id)
        self._storage.log_activity(device["name"], "Device forgotten.")

    def restart_device(self, device_id: str) -> None:
        device = self._storage.get_device(device_id)
        if not device:
            raise ValueError("Device not found.")
        provider = self._registry.get(device["provider_key"])
        account = self._storage.get_provider_account(device["provider_account_id"])
        runtime_device = dict(device)
        runtime_device["provider_credentials"] = (account or {}).get("credentials", {})
        try:
            provider.execute(runtime_device, "restart", {})
        except Exception:
            pass
        self._storage.log_activity(device["name"], "Restart command sent.")

    def voice_state_for_command(self, command: str) -> list[tuple[str, str]]:
        text = (command or "").strip()
        if not text:
            return [("Idle", "Waiting for wake word.")]
        return [
            ("Listening", text),
            ("Thinking", "Understanding command"),
            ("Executing", "Applying device action"),
            ("Completed", "Done"),
        ]

    def home_status(self) -> dict[str, Any]:
        devices = self.list_devices()
        return {
            "connected": len(devices) > 0,
            "device_count": len(devices),
            "time_ms": int(time.time() * 1000),
        }

    def execute_command(self, command: str) -> dict[str, Any]:
        text = self._normalize(command)
        if not text:
            raise ValueError("Smart home command is empty.")

        devices = self.list_devices()
        if not devices:
            raise ValueError("No smart home devices are connected yet.")

        action = self._guess_action(text)
        if not action:
            raise ValueError("I couldn't understand the smart home action.")

        # detect repeat/sequence patterns like "off and on 5 times"
        repeat_count = 1
        sequence_mode = None
        if "times" in text:
            num = self._extract_number(text)
            if num and num > 0:
                repeat_count = num
        # if user asks to "off and on" or "on and off", we'll perform power cycles
        if re.search(r"\b(off|turn off|switch off)\b.*\band\b.*\b(on|turn on|switch on)\b", text) or re.search(r"\b(on|turn on|switch on)\b.*\band\b.*\b(off|turn off|switch off)\b", text):
            sequence_mode = "power_cycle"

        targets = self._select_targets(text, devices)
        if not targets:
            raise ValueError("I couldn't find a matching smart home device.")

        results: list[str] = []
        for device in targets:
            device_id = str(device["id"])
            # handle sequence mode: power cycling
            if sequence_mode == "power_cycle":
                for i in range(repeat_count):
                    try:
                        # off
                        self.execute_device_action(device_id, "power", {"is_on": False})
                        time.sleep(0.3)
                        # on
                        self.execute_device_action(device_id, "power", {"is_on": True})
                        time.sleep(0.3)
                    except Exception:
                        pass
                results.append(f"Power-cycled {device.get('name')} {repeat_count} time(s)")
                continue

            # normal / repeated toggle if requested
            if repeat_count > 1 and action in ("power", "toggle"):
                for i in range(repeat_count):
                    payload = self._payload_for_device_action(text, device, action)
                    if action == "toggle":
                        payload = {"is_on": not bool(device.get("is_on"))}
                        action_name = "power"
                    else:
                        action_name = action
                    try:
                        response = self.execute_device_action(device_id, action_name, payload)
                        results.append(str(response.get("detail") or "Device updated."))
                    except Exception:
                        results.append("Device action failed")
                    time.sleep(0.2)
                continue

            payload = self._payload_for_device_action(text, device, action)
            if action == "toggle":
                payload = {"is_on": not bool(device.get("is_on"))}
                action_name = "power"
            else:
                action_name = action
            response = self.execute_device_action(device_id, action_name, payload)
            results.append(str(response.get("detail") or "Device updated."))

        detail = " ".join(results)
        return {
            "action": action,
            "targets": [str(device.get("name", "")) for device in targets],
            "detail": detail,
            "count": len(targets),
        }

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s%]", " ", (text or "").lower())).strip()

    def _guess_action(self, text: str) -> str | None:
        if any(word in text for word in ("restart", "reboot", "restart device", "reboot device")):
            return "restart"
        if "toggle" in text:
            return "toggle"
        if any(word in text for word in ("turn on", "switch on", "power on", "open", "start ", "activate", "enable")):
            return "power"
        if any(word in text for word in ("turn off", "switch off", "power off", "close", "stop ", "deactivate", "disable")):
            return "power"
        if any(word in text for word in ("speed", "fan speed")):
            return "speed"
        if any(word in text for word in ("brightness", "brighten", "dim", "light level")):
            return "brightness"
        if any(word in text for word in ("temperature", "color temp", "colour temp", "warmth")):
            return "temperature"
        if any(word in text for word in ("mode", "effect")):
            return "mode"
        # Fallback: if the text contains isolated 'on' or 'off', treat as power action
        if re.search(r"\b(on|off)\b", text):
            return "power"
        return None

    def _select_targets(self, text: str, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = self._normalize(text)
        if any(phrase in normalized for phrase in ("all devices", "everything", "whole house", "entire home", "all home", "switch everything", "turn everything")):
            return list(devices)

        room_hits = []
        for room in sorted({str(device.get("room", "")).strip() for device in devices if device.get("room")}, key=len, reverse=True):
            room_norm = self._normalize(room)
            if room_norm and room_norm in normalized:
                room_hits.append(room)
        if room_hits:
            room_set = {self._normalize(room) for room in room_hits}
            room_devices = [device for device in devices if self._normalize(str(device.get("room", ""))) in room_set]
            if room_devices:
                return room_devices

        name_matches = [
            device for device in devices
            if any(
                self._normalize(str(device.get(field, ""))) in normalized
                for field in ("name", "manufacturer", "external_id")
            )
        ]
        if name_matches:
            return name_matches

        type_hits = {
            "fan": ("fan", "ceiling fan", "table fan"),
            "light": ("light", "lights", "bulb", "lamp"),
            "plug": ("plug", "socket", "switch", "outlet"),
        }
        type_devices = []
        for device_type, keywords in type_hits.items():
            if any(word in normalized for word in keywords):
                type_devices.extend([device for device in devices if str(device.get("device_type", "")).lower() == device_type])
        if type_devices:
            return self._unique_devices(type_devices)

        if len(devices) == 1:
            return list(devices)
        return []

    def _payload_for_device_action(self, text: str, device: dict[str, Any], action: str) -> dict[str, Any]:
        normalized = self._normalize(text)
        if action == "power":
            if any(word in normalized for word in ("turn on", "switch on", "power on", "start", "activate", "enable")):
                return {"is_on": True}
            if any(word in normalized for word in ("turn off", "switch off", "power off", "close", "stop", "deactivate", "disable")):
                return {"is_on": False}
            return {"is_on": not bool(device.get("is_on"))}

        number = self._extract_number(normalized)
        if action == "speed":
            # detect keywords for max/min
            if "max" in normalized or "maximum" in normalized or "highest" in normalized:
                return {"speed": 6}
            if "min" in normalized or "lowest" in normalized or "lowest speed" in normalized:
                return {"speed": 1}
            return {"speed": max(1, min(6, number or self._infer_current_speed(device)))}
        if action == "brightness":
            return {"brightness": max(1, min(100, number or self._infer_current_brightness(device)))}
        if action == "temperature":
            return {"temperature": max(16, min(30, number or 24))}
        if action == "mode":
            mode = "Cool" if "cool" in normalized else "Auto"
            return {"mode": mode}
        if action == "restart":
            return {}
        return {}

    def _extract_number(self, text: str) -> int | None:
        match = re.search(r"\b(\d{1,3})\b", text)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        return None

    def _infer_current_speed(self, device: dict[str, Any]) -> int:
        traits = device.get("traits") or {}
        for key in ("speed", "last_recorded_speed"):
            value = traits.get(key)
            if value is not None:
                try:
                    return max(1, min(6, int(value)))
                except Exception:
                    continue
        return 1

    def _infer_current_brightness(self, device: dict[str, Any]) -> int:
        traits = device.get("traits") or {}
        for key in ("brightness", "last_recorded_brightness"):
            value = traits.get(key)
            if value is not None:
                try:
                    return max(1, min(100, int(value)))
                except Exception:
                    continue
        return 50

    def _unique_devices(self, devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for device in devices:
            device_id = str(device.get("id", ""))
            if device_id and device_id not in seen:
                seen.add(device_id)
                unique.append(device)
        return unique
