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

    async def async_calibrate_zone(self, zone: int) -> None:
        desc = self.zone_desc(zone)
        if desc is None:
            raise IrrigreenError(f"No directory entry for zone {zone}")
        await self.client.async_calibrate(desc)
        await self.async_request_refresh()

    async def async_test_devices(self) -> None:
        await self.client.async_test_devices()
        await self.async_request_refresh()

    async def async_scan_identify(self) -> None:
        await self.client.async_scan_identify()
        await self.async_request_refresh()

    # -- errors / system helpers ----------------------------------------------
    def device_errors(self) -> list[dict]:
        """Collected errors from every head and valve summary."""
        out: list[dict] = []
        for zone, s in ((self.data or {}).get("zone_summaries") or {}).items():
            msgs = s.get("error_messages") or []
            code = s.get("error_code") or 0
            if msgs or code:
                for z in (self.data or {}).get("dashboard", {}).get("enabled_zones", []):
                    if z.get("zone") == zone:
                        label = z.get("name") or f"Zone {zone}"
                        break
                else:
                    label = f"Zone {zone}"
                out.append({"device": label, "code": code, "messages": msgs})
        for valve, s in ((self.data or {}).get("valve_summaries") or {}).items():
            msgs = s.get("error_messages") or []
            if msgs:
                out.append({"device": f"Valve {valve}", "messages": msgs})
        return out

    @property
    def system_info(self) -> dict:
        return (self.data or {}).get("system_info") or {}

    @property
    def connection(self) -> dict:
        return (self.data or {}).get("connection") or {}

    @property
    def system_dashboard(self) -> dict:
        return (self.data or {}).get("system_dashboard") or {}

    @property
    def system_pref(self) -> dict:
        return (self.data or {}).get("system_pref") or {}

    def sprinkler_pref(self, zone: int) -> dict:
        return ((self.data or {}).get("sprinkler_prefs") or {}).get(zone) or {}

    def zone_type(self, zone: int) -> str | None:
        from .const import HEAD_TYPE_NAMES

        desc = self.zone_desc(zone) or {}
        t = desc.get("t")
        return HEAD_TYPE_NAMES.get(t, t)

    def zone_summary(self, zone: int) -> dict:
        return ((self.data or {}).get("zone_summaries") or {}).get(zone) or {}

    # -- setup banks / real heads ---------------------------------------------
    @property
    def _setups(self) -> dict:
        return (self.data or {}).get("setups") or {}

    def real_heads(self) -> list[dict]:
        """Every physically present head across setup banks (id != 0)."""
        heads: list[dict] = []
        for setup_num, setup in self._setups.items():
            for ig in (setup or {}).get("igsprinklers", []):
                if ig.get("id"):
                    heads.append({"setup": setup_num, **ig})
        return heads

    def valve_entries(self) -> list[dict]:
        """Every valve terminal across setup banks."""
        out: list[dict] = []
        for setup_num, setup in self._setups.items():
            for v in (setup or {}).get("valves", []):
                out.append({"setup": setup_num, **v})
        return out

    def _setup_for(self, key: str, num: int) -> int | None:
        for setup_num, setup in self._setups.items():
            for item in (setup or {}).get(key, []):
                if item.get("zone") == num:
                    return setup_num
        return None

    def head_enabled(self, zone: int) -> bool | None:
        for h in self.real_heads():
            if h.get("zone") == zone:
                return bool(h.get("enabled"))
        return None

    def valve_enabled(self, valve: int) -> bool | None:
        for v in self.valve_entries():
            if v.get("zone") == valve:
                return bool(v.get("enabled"))
        return None

    def _build_setup_body(
        self, setup: dict, ig_zone: int | None = None, valve_zone: int | None = None,
        value: bool = False,
    ) -> dict:
        return {
            "mast_valv": setup.get("mast_valv", 1),
            "igsprinklers": [
                {
                    "id": ig.get("id", 0),
                    "enabled": (value if ig.get("zone") == ig_zone else bool(ig.get("enabled"))),
                    "zone": ig.get("zone"),
                    "name": ig.get("name", ""),
                }
                for ig in setup.get("igsprinklers", [])
            ],
            "valves": [
                {
                    "enabled": (value if v.get("zone") == valve_zone else bool(v.get("enabled"))),
                    "zone": v.get("zone"),
                }
                for v in setup.get("valves", [])
            ],
        }

    async def async_set_zone_enabled(self, zone: int, enabled: bool) -> None:
        setup_num = self._setup_for("igsprinklers", zone)
        setup = self._setups.get(setup_num)
        if setup is None:
            raise IrrigreenError(f"No setup bank found for zone {zone}")
        await self.client.async_set_setup(setup_num, self._build_setup_body(setup, ig_zone=zone, value=enabled))
        await self.async_request_refresh()

    async def async_set_valve_enabled(self, valve: int, enabled: bool) -> None:
        setup_num = self._setup_for("valves", valve)
        setup = self._setups.get(setup_num)
        if setup is None:
            raise IrrigreenError(f"No setup bank found for valve {valve}")
        await self.client.async_set_setup(setup_num, self._build_setup_body(setup, valve_zone=valve, value=enabled))
        await self.async_request_refresh()

    # -- automatic watering + water adjustments --------------------------------
    @property
    def auto_water_on(self) -> bool:
        d = (self.data or {}).get("dashboard") or {}
        return bool(d.get("system_auto_water"))

    def system_water_adj(self) -> float | None:
        d = (self.data or {}).get("dashboard") or {}
        v = d.get("system_water_adj")
        return float(v) if v is not None else None

    def zone_water_adj(self, zone: int) -> float | None:
        for z in ((self.data or {}).get("dashboard") or {}).get("enabled_zones", []):
            if z.get("zone") == zone and z.get("water_adj") is not None:
                return float(z["water_adj"])
        return None

    def _current_system_adj(self) -> float:
        v = self.system_water_adj()
        # 0 is what the controller reports while auto-water is off; use 100% then.
        return v if v and v > 0 else 1

    async def async_set_auto_water(self, enabled: bool) -> None:
        await self.client.async_set_auto_water(enabled, self._current_system_adj())
        await self.async_request_refresh()

    async def async_set_system_water_adj(self, value: float) -> None:
        """Whole-system adjustment (1.0 = 100%). Only allowed while auto-water is on."""
        if not self.auto_water_on:
            raise IrrigreenError("Turn on automatic watering to change the system adjustment")
        await self.client.async_set_auto_water(True, round(value, 2))
        await self.async_request_refresh()

    async def async_set_zone_water_adj(self, zone: int, value: float) -> None:
        """Per-head adjustment, written the way the app does (all heads in the bank)."""
        if not self.auto_water_on:
            raise IrrigreenError("Turn on automatic watering to change head adjustments")
        setup_num = self._setup_for("igsprinklers", zone)
        if setup_num is None:
            raise IrrigreenError(f"No setup bank found for zone {zone}")
        bank_zones = {
            ig.get("zone") for ig in (self._setups.get(setup_num) or {}).get("igsprinklers", [])
        }
        heads = []
        for z in ((self.data or {}).get("dashboard") or {}).get("enabled_zones", []):
            zn = z.get("zone")
            if zn not in bank_zones:
                continue
            adj = round(value, 2) if zn == zone else z.get("water_adj")
            heads.append({"enabled": True, "zone": zn, "water_adj": adj})
        await self.client.async_set_setup(setup_num, {"igsprinklers": heads})
        await self.async_request_refresh()

    async def async_check_head_updates(self) -> None:
        await self.client.async_check_head_updates()
        await self.async_request_refresh()

    async def async_set_double_coverage(self, zone: int, enabled: bool) -> None:
        seed = self.sprinkler_pref(zone).get("seedUntil") or 0
        await self.client.async_set_double_coverage(zone, enabled, seed)
        await self.async_request_refresh()
