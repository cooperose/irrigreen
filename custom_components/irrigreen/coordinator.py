"""Polling coordinator for the Irrigreen controller."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IrrigreenClient, IrrigreenError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IrrigreenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the full controller state on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({host})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.host = host
        self.entry = entry
        self.client = IrrigreenClient(host, async_get_clientsession(hass))

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_all()
        except IrrigreenError as err:
            raise UpdateFailed(str(err)) from err

    # -- directory helpers (device -> run descriptor) --------------------------
    @property
    def _directory(self) -> dict[str, Any]:
        return (self.data or {}).get("directory") or {}

    def zone_desc(self, zone: int) -> dict | None:
        """Run descriptor for a sprinkler head by zone number."""
        for dev in self._directory.get("devices", []):
            if dev.get("zn") == zone and (dev.get("desc") or {}).get("t") != "v":
                return dev.get("desc")
        return None

    def valve_desc(self, valve: int) -> dict | None:
        """Run descriptor for a dumb valve by terminal/valve number."""
        for dev in self._directory.get("devices", []):
            desc = dev.get("desc") or {}
            if desc.get("t") == "v" and desc.get("term") == valve:
                return desc
        return None

    def schedule_idx(self, name: str) -> int | None:
        """Directory index for a schedule by its letter/legacy name."""
        for sched in self._directory.get("schedules", []):
            if sched.get("legacyName") == name:
                return sched.get("idx")
        return None

    async def async_run_zone(self, zone: int) -> None:
        desc = self.zone_desc(zone)
        if desc is None:
            raise IrrigreenError(f"No directory entry for zone {zone}")
        await self.client.async_run_desc(desc)
        await self.async_request_refresh()

    async def async_run_valve(self, valve: int) -> None:
        desc = self.valve_desc(valve)
        if desc is None:
            raise IrrigreenError(f"No directory entry for valve {valve}")
        await self.client.async_run_desc(desc)
        await self.async_request_refresh()

    async def async_stop(self) -> None:
        await self.client.async_stop()
        await self.async_request_refresh()

    async def async_set_schedule(self, name: str, enabled: bool) -> None:
        idx = self.schedule_idx(name)
        if idx is None:
            raise IrrigreenError(f"No schedule named {name}")
        await self.client.async_set_schedule_enabled(idx, enabled)
        await self.async_request_refresh()
