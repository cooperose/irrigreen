"""Number entities for Irrigreen: water adjustments (editable only with auto-water on)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
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
    entities: list[NumberEntity] = [SystemWaterAdjNumber(coordinator)]
    for zone in dashboard.get("enabled_zones", []):
        entities.append(ZoneWaterAdjNumber(coordinator, zone["zone"], zone.get("name")))
    async_add_entities(entities)


class _AdjBase(IrrigreenEntity, NumberEntity):
    """Percent slider; unavailable unless automatic watering is on."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:water-percent"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.auto_water_on


class SystemWaterAdjNumber(_AdjBase):
    _attr_native_min_value = 0
    _attr_native_max_value = 200

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "system_water_adj_set")
        self._attr_name = "Auto water: whole system"

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.system_water_adj()
        return round(v * 100) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_system_water_adj(value / 100)


class ZoneWaterAdjNumber(_AdjBase):
    _attr_native_min_value = 25
    _attr_native_max_value = 200

    def __init__(self, coordinator: IrrigreenCoordinator, zone: int, label: str | None) -> None:
        super().__init__(coordinator, f"zone{zone}_water_adj_set")
        self._zone = zone
        self._label = label or f"Zone {zone}"

    @property
    def name(self) -> str:
        return f"Auto water: {self._label}"

    @property
    def native_value(self) -> float | None:
        v = self.coordinator.zone_water_adj(self._zone)
        return round(v * 100) if v is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_zone_water_adj(self._zone, value / 100)
