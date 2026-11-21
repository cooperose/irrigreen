"""Polling coordinator for the Irrigreen controller."""
from __future__ import annotations

import logging
from datetime import timedelta
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
            data = await self.client.async_get_all()
        except IrrigreenError as err:
            raise UpdateFailed(str(err)) from err
        # Poll faster while a job is running so the UI and durations stay live.
        job = (data.get("job_status") or {}).get("data") or {}
        running = job.get("status") == "running"
        self.update_interval = timedelta(seconds=5 if running else 30)
        return data

    # -- running-job helpers (immediate, unlike the lagging dashboard status) ---
    def running_descs(self) -> list[dict]:
        job = (self.data or {}).get("job_status") or {}
        jdata = job.get("data") or {}
        if jdata.get("status") != "running":
            return []
        out: list[dict] = []
        for worker in jdata.get("entries") or []:
            for item in worker or []:
                if isinstance(item, list) and item and isinstance(item[0], dict):
                    out.append(item[0])
        return out

    def is_desc_running(self, desc: dict | None) -> bool:
        if not desc:
            return False
        for d in self.running_descs():
            if (
                d.get("t") == desc.get("t")
                and d.get("term") == desc.get("term")
                and d.get("id") == desc.get("id")
            ):
                return True
        return False

    def schedule_display_name(self, legacy: str) -> str:
        idx = self.schedule_idx(legacy)
        prefs = (self.data or {}).get("schedule_prefs") or {}
        pref = prefs.get(idx) or prefs.get(str(idx)) or {}
        return pref.get("userProvidedName") or f"Schedule {legacy}"

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
