"""Switches for Irrigreen: run zones/valves, and enable/disable schedules."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    for valve in dashboard.get("enabled_valves", []):
        entities.append(ValveRunSwitch(coordinator, valve["valve"]))
    for sched in schedules:
        if not sched.get("deleted"):
            entities.append(ScheduleEnableSwitch(coordinator, sched["name"]))

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
        for v in (self._dashboard or {}).get("enabled_valves", []):
            if v.get("valve") == self._valve_num:
                return str(v.get("status", "off")).lower() in RUNNING_STATES
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_run_valve(self._valve_num)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_stop()


class ScheduleEnableSwitch(IrrigreenEntity, SwitchEntity):
    """On/Off = enable/disable a schedule slot."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: IrrigreenCoordinator, name: str) -> None:
        super().__init__(coordinator, f"schedule_{name}_enabled")
        self._sched_name = name
        self._attr_name = f"Schedule {name} enabled"

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
