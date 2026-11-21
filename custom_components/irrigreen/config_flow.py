"""Config flow for Irrigreen."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IrrigreenClient, IrrigreenError
from .const import CONF_HOST, CONF_NAME, DEFAULT_NAME, DOMAIN


class IrrigreenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Irrigreen.

    On a segmented network the controller usually lives on its own VLAN, so
    mDNS discovery cannot reach it from Home Assistant. Entering the controller's
    IP address directly is the reliable path.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = IrrigreenClient(host, async_get_clientsession(self.hass))
            try:
                await client.async_probe()
            except IrrigreenError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or DEFAULT_NAME,
                    data={CONF_HOST: host, CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME)},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
