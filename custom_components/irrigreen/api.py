"""Thin async client for the Irrigreen controller's local HTTP API.

The controller speaks plain HTTP on port 80 with no authentication on the local
network. Read endpoints are GETs; control is done with small JSON POSTs whose
shapes were confirmed from the official app's own traffic:

  run a head/valve : POST /job/schedule/start
                     {"op":"run_desc","data":{"v":1,"desc":<desc>},"v":1}
  stop everything  : POST /job/exit            {}
  enable schedule  : POST /schedule_pref/<idx> {"v":2,"enabled":true|false}

A device "desc" comes straight from GET /directory, e.g.
  head  : {"v":2,"t":"s2ble","term":1,"id":61465}
  valve : {"v":2,"t":"v","term":1}
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import (
    EP_CONNECTION,
    EP_DASHBOARD,
    EP_DEVICE_STATUS,
    EP_DIRECTORY,
    EP_IGSPRINKLER,
    EP_JOB_CALIBRATE,
    EP_JOB_DIAGNOSTIC,
    EP_JOB_EXIT,
    EP_JOB_SCAN,
    EP_JOB_START,
    EP_JOB_STATUS,
    EP_PROBE,
    EP_SCHEDULES,
    EP_SCHEDULE_PREF,
    EP_SPRINKLER_PREF,
    EP_SYSTEM_INFO,
    EP_SYSTEM_PREF,
    EP_SYSTEM_SETUP,
    EP_VALVE,
    EP_ZONES_DASHBOARD,
    SETUPS,
)


class IrrigreenError(Exception):
    """Raised when the controller can't be reached or returns bad data."""


class IrrigreenClient:
    """Minimal client for one controller (read + control)."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host.strip().rstrip("/")
        self._session = session

    @property
    def base(self) -> str:
        host = self._host
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"
        return host

    async def _get(self, path: str) -> Any:
        url = f"{self.base}{path}"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    raise IrrigreenError(f"{path} returned HTTP {resp.status}")
                text = await resp.text()
                if not text.strip():
                    return None
                try:
                    return await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise IrrigreenError(f"{path} returned non-JSON: {err}") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise IrrigreenError(f"Cannot reach controller at {url}: {err}") from err

    async def _post(self, path: str, body: dict) -> Any:
        url = f"{self.base}{path}"
        try:
            async with self._session.post(
                url, json=body, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                text = await resp.text()
                if resp.status not in (200, 201, 204):
                    raise IrrigreenError(f"{path} returned HTTP {resp.status}: {text[:200]}")
                if not text.strip():
                    return None
                try:
                    return await resp.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    return text
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise IrrigreenError(f"POST {url} failed: {err}") from err

    # -- reads -----------------------------------------------------------------
    async def async_probe(self) -> dict[str, Any]:
        data = await self._get(EP_PROBE)
        if not isinstance(data, dict) or "enabled_zones" not in data:
            raise IrrigreenError("Host responded but does not look like an Irrigreen controller")
        return data

    async def async_get_all(self) -> dict[str, Any]:
        (
            dashboard, device, job, schedules, directory, sysinfo, connection,
            sysdash, syspref
        ) = await asyncio.gather(
            self._get(EP_ZONES_DASHBOARD),
            self._get(EP_DEVICE_STATUS),
            self._get(EP_JOB_STATUS),
            self._get(EP_SCHEDULES),
            self._get(EP_DIRECTORY),
            self._get(EP_SYSTEM_INFO),
            self._get(EP_CONNECTION),
            self._get(EP_DASHBOARD),
            self._get(EP_SYSTEM_PREF),
            return_exceptions=True,
        )

        def ok(value: Any) -> Any:
            return None if isinstance(value, Exception) else value

        if isinstance(dashboard, Exception):
            raise dashboard

        # Friendly schedule names live in /schedule_pref/<idx>; fetch per schedule.
        sched_prefs: dict[int, Any] = {}
        directory_ok = ok(directory)
        if isinstance(directory_ok, dict):
            idxs = [
                s.get("idx")
                for s in directory_ok.get("schedules", [])
                if s.get("idx") is not None
            ]
            if idxs:
                pref_results = await asyncio.gather(
                    *(self._get(f"{EP_SCHEDULE_PREF}/{i}") for i in idxs),
                    return_exceptions=True,
                )
                for i, r in zip(idxs, pref_results):
                    if isinstance(r, dict):
                        sched_prefs[i] = r

        # Per-device summaries, for error/stuck-valve detection.
        dash_ok = ok(dashboard) or {}
        zone_nums = [z.get("zone") for z in dash_ok.get("enabled_zones", [])]
        valve_nums = [v.get("valve") for v in dash_ok.get("enabled_valves", [])]
        zone_sum: dict[int, Any] = {}
        valve_sum: dict[int, Any] = {}
        sprinkler_prefs: dict[int, Any] = {}
        if zone_nums or valve_nums:
            nz, nv = len(zone_nums), len(valve_nums)
            results = await asyncio.gather(
                *(self._get(f"{EP_IGSPRINKLER}/{z}/summary") for z in zone_nums),
                *(self._get(f"{EP_VALVE}/{v}/summary") for v in valve_nums),
                *(self._get(f"{EP_SPRINKLER_PREF}/{z}") for z in zone_nums),
                return_exceptions=True,
            )
            for z, r in zip(zone_nums, results[:nz]):
                if isinstance(r, dict):
                    zone_sum[z] = r
            for v, r in zip(valve_nums, results[nz:nz + nv]):
                if isinstance(r, dict):
                    valve_sum[v] = r
            for z, r in zip(zone_nums, results[nz + nv:]):
                if isinstance(r, dict):
                    sprinkler_prefs[z] = r

        # Setup banks (zone/valve enable + names) for read-modify-write.
        setups: dict[int, Any] = {}
        setup_results = await asyncio.gather(
            *(self._get(f"{EP_SYSTEM_SETUP}/{n}") for n in SETUPS),
            return_exceptions=True,
        )
        for n, r in zip(SETUPS, setup_results):
            if isinstance(r, dict):
                setups[n] = r

        return {
            "dashboard": dashboard,
            "device_status": ok(device),
            "job_status": ok(job),
            "schedules": ok(schedules),
            "directory": directory_ok,
            "schedule_prefs": sched_prefs,
            "system_info": ok(sysinfo),
            "connection": ok(connection),
            "system_dashboard": ok(sysdash),
            "system_pref": ok(syspref),
            "zone_summaries": zone_sum,
            "valve_summaries": valve_sum,
            "sprinkler_prefs": sprinkler_prefs,
            "setups": setups,
        }

    # -- control ---------------------------------------------------------------
    async def async_run_desc(self, desc: dict) -> None:
        """Start a quick run of a single device descriptor (head or valve)."""
        await self._post(EP_JOB_START, {"op": "run_desc", "data": {"v": 1, "desc": desc}, "v": 1})

    async def async_stop(self) -> None:
        """Stop the current job (any running zone/valve/schedule)."""
        await self._post(EP_JOB_EXIT, {})

    async def async_set_schedule_enabled(self, idx: int, enabled: bool) -> None:
        """Enable or disable a schedule by its directory index."""
        await self._post(f"{EP_SCHEDULE_PREF}/{idx}", {"v": 2, "enabled": enabled})

    async def async_calibrate(self, desc: dict) -> None:
        """Calibrate a single head."""
        await self._post(
            EP_JOB_CALIBRATE,
            {
                "op": "calibrate",
                "v": 1,
                "data": {"v": 1, "desc": desc, "stabilizeTimeout": 60000, "maxRetries": 2},
            },
        )

    async def async_test_devices(self, update: bool = False) -> None:
        """Run the diagnostic 'scan_test' (checks devices, detects stuck valves)."""
        await self._post(
            EP_JOB_DIAGNOSTIC, {"op": "scan_test", "v": 1, "data": {"v": 1, "update": update}}
        )

    async def async_scan_identify(self) -> None:
        """Scan/identify devices on the bus."""
        await self._post(EP_JOB_SCAN, {"op": "scan", "v": 1})

    async def async_set_double_coverage(self, zone: int, enabled: bool, seed_until: int = 0) -> None:
        """Set a head's double-coverage preference (the app's 'save' action)."""
        await self._post(
            f"{EP_SPRINKLER_PREF}/{zone}",
            {"v": 1, "doubleCoverage": enabled, "seedUntil": seed_until},
        )

    async def async_set_setup(self, setup_num: int, body: dict) -> None:
        """Write a full setup bank (zone/valve enable + names)."""
        await self._post(f"{EP_SYSTEM_SETUP}/{setup_num}", body)
