"""Thin async client for the Irrigreen controller's local HTTP API.

The controller speaks plain HTTP on port 80 with no authentication on the local
network. This client only performs read-only GET requests in v0.1. Control
(POST) endpoints will be added once their payloads are confirmed.
"""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import (
    EP_DEVICE_STATUS,
    EP_JOB_STATUS,
    EP_PROBE,
    EP_SCHEDULES,
    EP_ZONES_DASHBOARD,
)


class IrrigreenError(Exception):
    """Raised when the controller can't be reached or returns bad data."""


class IrrigreenClient:
    """Minimal read-only client for one controller."""

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

    async def async_probe(self) -> dict[str, Any]:
        """Confirm this host is an Irrigreen controller; returns the dashboard."""
        data = await self._get(EP_PROBE)
        if not isinstance(data, dict) or "enabled_zones" not in data:
            raise IrrigreenError("Host responded but does not look like an Irrigreen controller")
        return data

    async def async_get_all(self) -> dict[str, Any]:
        """Fetch every read-only endpoint. Missing/empty ones become None."""
        dashboard, device, job, schedules = await asyncio.gather(
            self._get(EP_ZONES_DASHBOARD),
            self._get(EP_DEVICE_STATUS),
            self._get(EP_JOB_STATUS),
            self._get(EP_SCHEDULES),
            return_exceptions=True,
        )

        def ok(value: Any) -> Any:
            return None if isinstance(value, Exception) else value

        # The dashboard is required; if it failed, surface the error.
        if isinstance(dashboard, Exception):
            raise dashboard

        return {
            "dashboard": dashboard,
            "device_status": ok(device),
            "job_status": ok(job),
            "schedules": ok(schedules),
        }
