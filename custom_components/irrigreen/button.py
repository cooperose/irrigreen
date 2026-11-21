"""Buttons for Irrigreen: stop, test/scan devices, and per-head calibrate."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import IrrigreenCoordinator
from .entity import IrrigreenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IrrigreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    dashboard = (coordinator.data or {}).get("dashboard") or {}

    entities: list[ButtonEntity] = [
        StopAllButton(coordinator),
        TestDevicesButton(coordinator),
        ScanDevicesButton(coordinator),
    ]
    for zone in dashboard.get("enabled_zones", []):
        entities.append(CalibrateZoneButton(coordinator, zone["zone"]))

    async_add_entities(entities)


class StopAllButton(IrrigreenEntity, ButtonEntity):
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "stop_all")
        self._attr_name = "Stop all watering"

    async def async_press(self) -> None:
        await self.coordinator.async_stop()


class TestDevicesButton(IrrigreenEntity, ButtonEntity):
    """Run the diagnostic scan-test (checks heads/valves, detects stuck valves)."""

    _attr_icon = "mdi:clipboard-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "test_devices")
        self._attr_name = "Test devices"

    async def async_press(self) -> None:
        await self.coordinator.async_test_devices()


class ScanDevicesButton(IrrigreenEntity, ButtonEntity):
    """Scan/identify devices on the bus."""

    _attr_icon = "mdi:magnify-scan"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "scan_devices")
        self._attr_name = "Scan for devices"

    async def async_press(self) -> None:
        await self.coordinator.async_scan_identify()


class CalibrateZoneButton(IrrigreenEntity, ButtonEntity):
    _attr_icon = "mdi:target"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int) -> None:
        super().__init__(coordinator, f"zone{zone_num}_calibrate")
        self._zone_num = zone_num

    @property
    def name(self) -> str:
        z = self.coordinator.zone_summary(self._zone_num)
        for zz in (self.coordinator.data or {}).get("dashboard", {}).get("enabled_zones", []):
            if zz.get("zone") == self._zone_num:
                return f"{zz.get('name') or f'Zone {self._zone_num}'} calibrate"
        return f"Zone {self._zone_num} calibrate"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.zone_desc(self._zone_num) is not None

    async def async_press(self) -> None:
        await self.coordinator.async_calibrate_zone(self._zone_num)
