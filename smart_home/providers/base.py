from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderField:
    key: str
    label: str
    placeholder: str = ""
    secret: bool = False


class SmartHomeProvider:
    key = "base"
    name = "Base Provider"
    available = True
    coming_soon = False

    def auth_fields(self) -> list[ProviderField]:
        return []

    def authenticate(self, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"account_label": self.name, "credentials": credentials}

    def discover_devices(self, credentials: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def disconnect(self, credentials: dict[str, Any]) -> bool:
        return True

    def execute(self, device: dict[str, Any], action: str, payload: dict[str, Any]) -> dict[str, Any]:
        traits = dict(device.get("traits") or {})
        if action == "power":
            return {"is_on": bool(payload.get("is_on")), "traits": traits, "detail": f"{device['name']} power updated."}
        return {"is_on": bool(device.get("is_on")), "traits": traits, "detail": f"{device['name']} updated."}

    def get_status(self, device: dict[str, Any]) -> dict[str, Any]:
        return {"online": True, "detail": f"{device['name']} available."}
