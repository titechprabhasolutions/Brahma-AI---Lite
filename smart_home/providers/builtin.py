from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from typing import Any

import requests

from .base import ProviderField, SmartHomeProvider


ATOMBERG_BASE_URL = "https://api.developer.atomberg-iot.com"


def _clean_text(value: Any, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    raw = parts[1]
    padding = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode((raw + padding).encode("utf-8"))
        payload = json.loads(decoded.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


class AtombergCloudClient:
    def __init__(self, api_key: str, refresh_token: str):
        self._api_key = api_key.strip()
        self._refresh_token = refresh_token.strip()
        self._access_token: str | None = None

    def _request(
        self,
        path: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        request_headers = {
            "X-API-Key": self._api_key,
        }
        if headers:
            request_headers.update(headers)
        url = f"{ATOMBERG_BASE_URL}{path}"
        return requests.request(method, url, headers=request_headers, json=body, timeout=20)

    def _ensure_access_token(self) -> str:
        if self._access_token:
            payload = _jwt_payload(self._access_token)
            exp = payload.get("exp")
            if isinstance(exp, (int, float)) and time.time() < float(exp) - 30:
                return self._access_token

        resp = self._request(
            "/v1/get_access_token",
            headers={"Authorization": f"Bearer {self._refresh_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "Success":
            raise ValueError(str(data.get("message") or "Failed to get Atomberg access token."))
        token = data["message"]["access_token"]
        self._access_token = str(token)
        return self._access_token

    def _authorized_request(
        self,
        path: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> requests.Response:
        token = self._ensure_access_token()
        resp = self._request(path, method=method, body=body, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 401:
            self._access_token = None
            token = self._ensure_access_token()
            resp = self._request(path, method=method, body=body, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp

    def list_devices(self) -> list[dict[str, Any]]:
        resp = self._authorized_request("/v1/get_list_of_devices")
        data = resp.json()
        if data.get("status") != "Success":
            raise ValueError(str(data.get("message") or "Failed to list Atomberg devices."))
        devices = data.get("message", {}).get("devices_list", [])
        return devices if isinstance(devices, list) else []

    def device_state(self) -> list[dict[str, Any]]:
        resp = self._authorized_request("/v1/get_device_state?device_id=all")
        data = resp.json()
        if data.get("status") != "Success":
            raise ValueError(str(data.get("message") or "Failed to read Atomberg state."))
        states = data.get("message", {}).get("device_state", [])
        return states if isinstance(states, list) else []

    def send_command(self, device_id: str, command: dict[str, Any]) -> bool:
        resp = self._authorized_request(
            "/v1/send_command",
            method="POST",
            body={"device_id": device_id, "command": command},
        )
        data = resp.json()
        return data.get("status") == "Success"


class AtombergProvider(SmartHomeProvider):
    key = "atomberg"
    name = "Atomberg Home"
    manufacturer = "Atomberg"

    def auth_fields(self) -> list[ProviderField]:
        return [
            ProviderField("api_key", "API Key", "Atomberg developer API key"),
            ProviderField("refresh_token", "Refresh Token", "Atomberg refresh token", secret=True),
        ]

    def authenticate(self, credentials: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(credentials.get("api_key"))
        refresh_token = _clean_text(credentials.get("refresh_token"))
        if not api_key or not refresh_token:
            raise ValueError("Atomberg API key and refresh token are required.")
        label = "Atomberg Home"
        client = AtombergCloudClient(api_key, refresh_token)
        # Validate the connection immediately so the setup flow fails fast on bad auth.
        client.list_devices()
        return {
            "account_label": label,
            "credentials": {
                "api_key": api_key,
                "refresh_token": refresh_token,
            },
        }

    def discover_devices(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        client = AtombergCloudClient(
            _clean_text(credentials.get("api_key")),
            _clean_text(credentials.get("refresh_token")),
        )
        devices = client.list_devices()
        states = client.device_state()
        state_map = {str(item.get("device_id")): item for item in states if item.get("device_id")}
        results: list[dict[str, Any]] = []
        for device in devices:
            device_id = str(device.get("device_id") or "").strip()
            if not device_id:
                continue
            state = dict(state_map.get(device_id, {}))
            results.append(
                {
                    "external_id": device_id,
                    "name": _clean_text(device.get("name"), "Atomberg Fan"),
                    "manufacturer": self.manufacturer,
                    "room": _clean_text(device.get("room"), "Home"),
                    "device_type": "fan",
                    "image_key": "fan",
                    "is_on": bool(state.get("power", state.get("is_on", False))),
                    "traits": {
                        "device_id": device_id,
                        "series": _clean_text(device.get("series")),
                        "model": _clean_text(device.get("model")),
                        "color": _clean_text(device.get("color")),
                        "speed": _safe_int(state.get("speed", state.get("last_recorded_speed", 1)) or 1, 1),
                        "sleep": bool(state.get("sleep", state.get("sleep_mode", False))),
                        "led": bool(state.get("led", state.get("light", False))),
                        "brightness": _safe_int(state.get("brightness") or state.get("last_recorded_brightness") or 0, 0),
                        "light_mode": state.get("light_mode") or state.get("last_recorded_color"),
                        "timer_hours": state.get("timer_hours"),
                        "timer_time_elapsed_mins": state.get("timer_time_elapsed_mins"),
                    },
                }
            )
        return results

    def execute(self, device: dict[str, Any], action: str, payload: dict[str, Any]) -> dict[str, Any]:
        creds = dict(device.get("provider_credentials") or {})
        if not creds.get("api_key") or not creds.get("refresh_token"):
            raise ValueError("Atomberg credentials are missing.")
        client = AtombergCloudClient(creds["api_key"], creds["refresh_token"])
        device_id = str(device.get("external_id") or device.get("traits", {}).get("device_id") or "")
        if not device_id:
            raise ValueError("Atomberg device id is missing.")

        command: dict[str, Any] | None = None
        detail = f"{device['name']} updated."
        if action == "power":
            is_on = bool(payload.get("is_on"))
            command = {"power": is_on}
            detail = f"{device['name']} turned {'on' if is_on else 'off'}."
        elif action == "speed":
            speed = max(1, min(6, int(payload.get("speed", 1))))
            command = {"speed": speed}
            detail = f"{device['name']} speed set to {speed}."
        elif action == "brightness":
            brightness = max(1, min(100, int(payload.get("brightness", 50))))
            command = {"brightness": brightness}
            detail = f"{device['name']} brightness set to {brightness}%."
        elif action == "temperature":
            temperature = max(16, min(30, int(payload.get("temperature", 24))))
            command = {"temperature": temperature}
            detail = f"{device['name']} temperature set to {temperature} C."
        elif action == "mode":
            mode = _clean_text(payload.get("mode"), "Cool")
            command = {"light_mode": mode.lower()}
            detail = f"{device['name']} mode set to {mode}."
        elif action == "sleep":
            enabled = bool(payload.get("enabled", True))
            command = {"sleep": enabled}
            detail = f"{device['name']} sleep mode {'enabled' if enabled else 'disabled'}."
        elif action == "timer":
            timer = max(0, min(6, int(payload.get("timer", 0))))
            command = {"timer": timer}
            detail = f"{device['name']} timer set to {timer} hour(s)."
        elif action == "led":
            enabled = bool(payload.get("enabled", True))
            command = {"led": enabled}
            detail = f"{device['name']} LED {'enabled' if enabled else 'disabled'}."

        if command:
            client.send_command(device_id, command)

        refreshed = self._refresh_atomberg_state(client, device_id)
        is_on = bool(refreshed.get("is_on", device.get("is_on")))
        traits = dict(device.get("traits") or {})
        traits.update(refreshed)
        if "power" in refreshed:
            traits["power"] = refreshed["power"]
        return {"is_on": is_on, "traits": traits, "detail": detail}

    def _refresh_atomberg_state(self, client: AtombergCloudClient, device_id: str) -> dict[str, Any]:
        states = client.device_state()
        for state in states:
            if str(state.get("device_id")) != device_id:
                continue
            result = dict(state)
            result["is_on"] = bool(result.get("power", result.get("is_on", False)))
            if "last_recorded_speed" in result and "speed" not in result:
                result["speed"] = result.get("last_recorded_speed")
            if "sleep_mode" in result and "sleep" not in result:
                result["sleep"] = result.get("sleep_mode")
            if "last_recorded_brightness" in result and "brightness" not in result:
                result["brightness"] = result.get("last_recorded_brightness")
            if "last_recorded_color" in result and "light_mode" not in result:
                result["light_mode"] = result.get("last_recorded_color")
            return result
        return {}


class KasaProvider(SmartHomeProvider):
    key = "kasa"
    name = "TP-Link Kasa"
    manufacturer = "TP-Link Kasa"

    def auth_fields(self) -> list[ProviderField]:
        return [
            ProviderField("host", "Device IP / Host", "Optional - leave empty to scan the network"),
            ProviderField("username", "Username", "Optional cloud username"),
            ProviderField("password", "Password", "Optional cloud password", secret=True),
        ]

    def authenticate(self, credentials: dict[str, Any]) -> dict[str, Any]:
        host = _clean_text(credentials.get("host"))
        username = _clean_text(credentials.get("username"))
        password = _clean_text(credentials.get("password"))
        return {
            "account_label": host or "Kasa Home",
            "credentials": {
                "host": host,
                "username": username,
                "password": password,
            },
        }

    def discover_devices(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        return asyncio.run(self._discover_async(credentials))

    def execute(self, device: dict[str, Any], action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self._execute_async(device, action, payload))

    async def _discover_async(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            from kasa import Discover
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("python-kasa is not installed. Install requirements.txt first.") from exc

        host = _clean_text(credentials.get("host"))
        username = _clean_text(credentials.get("username")) or None
        password = _clean_text(credentials.get("password")) or None

        devices: list[Any] = []
        if host:
            found = await Discover.discover_single(host, username=username, password=password)
            devices = [found]
        else:
            discovered = await Discover.discover(username=username, password=password)
            devices = list(discovered.values())

        results: list[dict[str, Any]] = []
        for kasa_device in devices:
            try:
                await kasa_device.update()
            except Exception:
                pass
            results.append(self._to_record(kasa_device, credentials))
        return results

    async def _execute_async(self, device: dict[str, Any], action: str, payload: dict[str, Any]) -> dict[str, Any]:
        kasa_device = await self._connect_device(device)
        detail = f"{device['name']} updated."
        if action == "power":
            if bool(payload.get("is_on")):
                await kasa_device.turn_on()
                detail = f"{device['name']} turned on."
            else:
                await kasa_device.turn_off()
                detail = f"{device['name']} turned off."
        elif action == "brightness":
            value = max(1, min(100, int(payload.get("brightness", 50))))
            await self._set_brightness(kasa_device, value)
            detail = f"{device['name']} brightness set to {value}%."
        elif action == "temperature":
            value = max(2500, min(6500, int(payload.get("temperature", 3000))))
            await self._set_color_temp(kasa_device, value)
            detail = f"{device['name']} color temperature set to {value}K."
        elif action == "mode":
            mode = _clean_text(payload.get("mode"), "Auto")
            await self._set_effect(kasa_device, mode)
            detail = f"{device['name']} effect set to {mode}."
        elif action == "restart":
            await kasa_device.reboot()
            detail = f"{device['name']} rebooting."

        try:
            await kasa_device.update()
        except Exception:
            pass
        refreshed = self._to_record(kasa_device, device.get("provider_credentials") or {})
        traits = dict(device.get("traits") or {})
        traits.update(refreshed.get("traits", {}))
        return {"is_on": refreshed.get("is_on", bool(device.get("is_on"))), "traits": traits, "detail": detail}

    def _to_record(self, kasa_device: Any, credentials: dict[str, Any]) -> dict[str, Any]:
        alias = _clean_text(getattr(kasa_device, "alias", None)) or _clean_text(getattr(kasa_device, "model", None), "Kasa Device")
        host = _clean_text(getattr(kasa_device, "host", None))
        device_type = self._infer_device_type(kasa_device)
        traits: dict[str, Any] = {
            "host": host,
            "mac": _clean_text(getattr(kasa_device, "mac", None)),
            "model": _clean_text(getattr(kasa_device, "model", None)),
            "device_family": _clean_text(getattr(kasa_device, "device_type", None)),
        }
        for attr in ("brightness", "color_temp", "hsv", "temperature", "signal_level", "rssi"):
            if hasattr(kasa_device, attr):
                value = getattr(kasa_device, attr)
                if value is not None:
                    traits[attr] = value if not hasattr(value, "to_dict") else value.to_dict()
        traits["supports_brightness"] = hasattr(kasa_device, "set_brightness") or ("brightness" in traits)
        traits["supports_color_temp"] = hasattr(kasa_device, "set_color_temp") or ("color_temp" in traits)
        return {
            "external_id": host or alias,
            "name": alias,
            "manufacturer": self.manufacturer,
            "room": "Home",
            "device_type": device_type,
            "image_key": device_type,
            "is_on": bool(getattr(kasa_device, "is_on", False)),
            "traits": traits,
            "provider_credentials": credentials,
        }

    def _infer_device_type(self, kasa_device: Any) -> str:
        klass = type(kasa_device).__name__.lower()
        model = _clean_text(getattr(kasa_device, "model", "")).lower()
        if "bulb" in klass or model.startswith("l"):
            return "light"
        if "strip" in klass:
            return "light"
        if "switch" in klass:
            return "switch"
        if "plug" in klass or model.startswith(("hs1", "kp1", "ep1")):
            return "plug"
        return "device"

    async def _connect_device(self, device: dict[str, Any]) -> Any:
        try:
            from kasa import Discover
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("python-kasa is not installed. Install requirements.txt first.") from exc

        traits = device.get("traits") or {}
        host = _clean_text(traits.get("host")) or _clean_text(device.get("external_id"))
        if not host:
            raise ValueError("Kasa device host is missing.")
        creds = device.get("provider_credentials") or {}
        username = _clean_text(creds.get("username")) or None
        password = _clean_text(creds.get("password")) or None
        kasa_device = await Discover.discover_single(host, username=username, password=password)
        await kasa_device.update()
        return kasa_device

    async def _set_brightness(self, kasa_device: Any, brightness: int) -> None:
        from kasa import Module

        if hasattr(kasa_device, "set_brightness"):
            await kasa_device.set_brightness(brightness)
            return
        light = getattr(kasa_device, "modules", {}).get(Module.Light) if hasattr(kasa_device, "modules") else None
        if light and hasattr(light, "set_brightness"):
            await light.set_brightness(brightness)
            return
        raise ValueError("Brightness control is not supported by this Kasa device.")

    async def _set_color_temp(self, kasa_device: Any, temperature: int) -> None:
        from kasa import Module

        if hasattr(kasa_device, "set_color_temp"):
            await kasa_device.set_color_temp(temperature)
            return
        if hasattr(kasa_device, "set_color_temp_kelvin"):
            await kasa_device.set_color_temp_kelvin(temperature)
            return
        light = getattr(kasa_device, "modules", {}).get(Module.Light) if hasattr(kasa_device, "modules") else None
        if light and hasattr(light, "set_color_temp"):
            await light.set_color_temp(temperature)
            return
        if light and hasattr(light, "set_color_temp_kelvin"):
            await light.set_color_temp_kelvin(temperature)
            return
        raise ValueError("Color temperature is not supported by this Kasa device.")

    async def _set_effect(self, kasa_device: Any, effect: str) -> None:
        from kasa import Module

        modules = getattr(kasa_device, "modules", {}) if hasattr(kasa_device, "modules") else {}
        light_effect = None
        if hasattr(modules, "get"):
            light_effect = modules.get(Module.LightEffect)
        if light_effect and hasattr(light_effect, "set_effect"):
            await light_effect.set_effect(effect)
            return
        raise ValueError("Effect control is not supported by this Kasa device.")


def built_in_provider_classes() -> list[type[SmartHomeProvider]]:
    return [AtombergProvider, KasaProvider]
