"""Buttons for Irrigreen (stop all watering)."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IrrigreenCoordinator
from .entity import IrrigreenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IrrigreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([StopAllButton(coordinator)])


class StopAllButton(IrrigreenEntity, ButtonEntity):
    _attr_icon = "mdi:stop"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "stop_all")
        self._attr_name = "Stop all watering"
        self._attr_device_class = None

    async def async_press(self) -> None:
        await self.coordinator.async_stop()
