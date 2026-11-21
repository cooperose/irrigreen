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
    EP_DEVICE_STATUS,
    EP_DIRECTORY,
    EP_JOB_EXIT,
    EP_JOB_START,
    EP_JOB_STATUS,
    EP_PROBE,
    EP_SCHEDULES,
    EP_SCHEDULE_PREF,
    EP_ZONES_DASHBOARD,
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
        dashboard, device, job, schedules, directory = await asyncio.gather(
            self._get(EP_ZONES_DASHBOARD),
            self._get(EP_DEVICE_STATUS),
            self._get(EP_JOB_STATUS),
            self._get(EP_SCHEDULES),
            self._get(EP_DIRECTORY),
            return_exceptions=True,
        )

        def ok(value: Any) -> Any:
            return None if isinstance(value, Exception) else value

        if isinstance(dashboard, Exception):
            raise dashboard

        return {
            "dashboard": dashboard,
            "device_status": ok(device),
            "job_status": ok(job),
            "schedules": ok(schedules),
            "directory": ok(directory),
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
