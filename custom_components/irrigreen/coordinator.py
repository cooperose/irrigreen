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
