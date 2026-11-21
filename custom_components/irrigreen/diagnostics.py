"""Diagnostics for Irrigreen — dumps the raw controller payloads.

Download from the device page in Home Assistant. Addresses, serials and Wi-Fi
names are not expected in these local endpoints, but the dump is passed through
a light redactor as a safety net before it leaves your system.
"""
from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IrrigreenCoordinator

_SENSITIVE = re.compile(r"(serial|mac|ssid|passkey|password|token|lat|lon|address|email|phone)", re.I)


def _redact(obj: Any, key: str = "") -> Any:
    if isinstance(obj, dict):
        return {k: _redact(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v, key) for v in obj]
    if key and _SENSITIVE.search(key):
        return "**REDACTED**"
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: IrrigreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "host": "**REDACTED**",
        "data": _redact(coordinator.data or {}),
    }
