"""Services (actions) for Irrigreen automations."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import IrrigreenCoordinator

SERVICE_RUN_ZONE = "run_zone"
SERVICE_RUN_VALVE = "run_valve"
SERVICE_STOP = "stop"
SERVICE_SET_SCHEDULE = "set_schedule"


def _coordinators(hass: HomeAssistant) -> list[IrrigreenCoordinator]:
    return list(hass.data.get(DOMAIN, {}).values())


def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_STOP):
        return

    async def _run_zone(call: ServiceCall) -> None:
        zone = call.data["zone"]
        for c in _coordinators(hass):
            if c.zone_desc(zone) is not None:
                await c.async_run_zone(zone)

    async def _run_valve(call: ServiceCall) -> None:
        valve = call.data["valve"]
        for c in _coordinators(hass):
            if c.valve_desc(valve) is not None:
                await c.async_run_valve(valve)

    async def _stop(call: ServiceCall) -> None:
        for c in _coordinators(hass):
            await c.async_stop()

    async def _set_schedule(call: ServiceCall) -> None:
        name = call.data["name"]
        enabled = call.data["enabled"]
        for c in _coordinators(hass):
            if c.schedule_idx(name) is not None:
                await c.async_set_schedule(name, enabled)

    hass.services.async_register(
        DOMAIN, SERVICE_RUN_ZONE, _run_zone,
        schema=vol.Schema({vol.Required("zone"): cv.positive_int}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RUN_VALVE, _run_valve,
        schema=vol.Schema({vol.Required("valve"): cv.positive_int}),
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, _stop, schema=vol.Schema({}))
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SCHEDULE, _set_schedule,
        schema=vol.Schema(
            {vol.Required("name"): cv.string, vol.Required("enabled"): cv.boolean}
        ),
    )
