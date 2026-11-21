"""Switches for Irrigreen: run zones/valves, and enable/disable schedules."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RUNNING_STATES
from .coordinator import IrrigreenCoordinator
from .entity import IrrigreenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: IrrigreenCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    dashboard = data.get("dashboard") or {}
    schedules = (data.get("schedules") or {}).get("schedules", []) if isinstance(
        data.get("schedules"), dict
    ) else []

    entities: list[SwitchEntity] = []
    for zone in dashboard.get("enabled_zones", []):
        entities.append(ZoneRunSwitch(coordinator, zone["zone"]))
        entities.append(DoubleCoverageSwitch(coordinator, zone["zone"]))
    for valve in dashboard.get("enabled_valves", []):
        entities.append(ValveRunSwitch(coordinator, valve["valve"]))
    for sched in schedules:
        if not sched.get("deleted"):
            entities.append(ScheduleEnableSwitch(coordinator, sched["name"]))
    # Enable/disable every physically present head.
    for head in coordinator.real_heads():
        entities.append(ZoneEnableSwitch(coordinator, head["zone"], head.get("name")))
    # Enable/disable every valve terminal.
    for v in coordinator.valve_entries():
        entities.append(ValveEnableSwitch(coordinator, v["zone"]))
    # System-wide automatic (weather-based) watering.
    entities.append(AutoWaterSwitch(coordinator))

    async_add_entities(entities)


class ZoneRunSwitch(IrrigreenEntity, SwitchEntity):
    """On = quick-run this head; Off = stop the current job."""

    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int) -> None:
        super().__init__(coordinator, f"zone{zone_num}_run")
        self._zone_num = zone_num

    def _zone(self) -> dict | None:
        for z in (self._dashboard or {}).get("enabled_zones", []):
            if z.get("zone") == self._zone_num:
                return z
        return None

    @property
    def name(self) -> str:
        z = self._zone()
        return f"{z.get('name') if z else f'Zone {self._zone_num}'} run"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.zone_desc(self._zone_num) is not None

    @property
    def is_on(self) -> bool | None:
        # Prefer the live job (updates instantly); fall back to dashboard status.
        if self.coordinator.is_desc_running(self.coordinator.zone_desc(self._zone_num)):
            return True
        z = self._zone()
        if z is None:
            return None
        return str(z.get("status", "off")).lower() in RUNNING_STATES

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_zone(self._zone_num)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_stop()


class ValveRunSwitch(IrrigreenEntity, SwitchEntity):
    """On = quick-run this valve; Off = stop the current job."""

    _attr_icon = "mdi:pipe-valve"

    def __init__(self, coordinator: IrrigreenCoordinator, valve_num: int) -> None:
        super().__init__(coordinator, f"valve{valve_num}_run")
        self._valve_num = valve_num
        self._attr_name = f"Valve {valve_num} run"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.valve_desc(self._valve_num) is not None

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.is_desc_running(self.coordinator.valve_desc(self._valve_num)):
            return True
        for v in (self._dashboard or {}).get("enabled_valves", []):
            if v.get("valve") == self._valve_num:
                return str(v.get("status", "off")).lower() in RUNNING_STATES
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_valve(self._valve_num)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_stop()


class DoubleCoverageSwitch(IrrigreenEntity, SwitchEntity):
    """Per-head double coverage (writes /sprinkler_pref/<zone>)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:circle-multiple"

    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int) -> None:
        super().__init__(coordinator, f"zone{zone_num}_double_coverage")
        self._zone_num = zone_num

    def _label(self) -> str:
        for z in (self._dashboard or {}).get("enabled_zones", []):
            if z.get("zone") == self._zone_num:
                return z.get("name") or f"Zone {self._zone_num}"
        return f"Zone {self._zone_num}"

    @property
    def name(self) -> str:
        return f"{self._label()} double coverage"

    @property
    def is_on(self) -> bool | None:
        pref = self.coordinator.sprinkler_pref(self._zone_num)
        return pref.get("doubleCoverage") if "doubleCoverage" in pref else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_double_coverage(self._zone_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_double_coverage(self._zone_num, False)


class ZoneEnableSwitch(IrrigreenEntity, SwitchEntity):
    """Enable/disable a head (writes the setup bank)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int, label: str | None) -> None:
        super().__init__(coordinator, f"zone{zone_num}_enabled")
        self._zone_num = zone_num
        self._label = label or f"Zone {zone_num}"

    @property
    def name(self) -> str:
        return f"{self._label} enabled"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.head_enabled(self._zone_num)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_enabled(self._zone_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_zone_enabled(self._zone_num, False)


class ValveEnableSwitch(IrrigreenEntity, SwitchEntity):
    """Enable/disable a valve terminal (writes the setup bank)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: IrrigreenCoordinator, valve_num: int) -> None:
        super().__init__(coordinator, f"valve{valve_num}_enabled")
        self._valve_num = valve_num
        self._attr_name = f"Valve {valve_num} enabled"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.valve_enabled(self._valve_num)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_valve_enabled(self._valve_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_valve_enabled(self._valve_num, False)


class AutoWaterSwitch(IrrigreenEntity, SwitchEntity):
    """Weather-based automatic watering (writes /system_pref awEnabled)."""

    _attr_icon = "mdi:weather-partly-rainy"

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "auto_water")
        self._attr_name = "Automatic watering"

    @property
    def is_on(self) -> bool | None:
        pref = self.coordinator.system_pref
        if "awEnabled" in pref:
            return bool(pref.get("awEnabled"))
        d = self._dashboard or {}
        return bool(d.get("system_auto_water")) if "system_auto_water" in d else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_auto_water(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_auto_water(False)


class ScheduleEnableSwitch(IrrigreenEntity, SwitchEntity):
    """On/Off = enable/disable a schedule slot."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: IrrigreenCoordinator, name: str) -> None:
        super().__init__(coordinator, f"schedule_{name}_enabled")
        self._sched_name = name

    @property
    def name(self) -> str:
        return f"{self.coordinator.schedule_display_name(self._sched_name)} enabled"

    def _sched(self) -> dict | None:
        for s in (self._schedules or []):
            if s.get("name") == self._sched_name:
                return s
        return None

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.schedule_idx(self._sched_name) is not None

    @property
    def is_on(self) -> bool | None:
        s = self._sched()
        return bool(s.get("enabled")) if s else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_schedule(self._sched_name, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_schedule(self._sched_name, False)
