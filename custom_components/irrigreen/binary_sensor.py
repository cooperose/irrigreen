"""Binary sensors for Irrigreen (watering state, valves, sensors, job)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    data = coordinator.data or {}
    dashboard = data.get("dashboard") or {}
    device = data.get("device_status") or {}

    entities: list[BinarySensorEntity] = []

    for zone in dashboard.get("enabled_zones", []):
        entities.append(ZoneWateringBinarySensor(coordinator, zone["zone"]))
    for valve in dashboard.get("enabled_valves", []):
        entities.append(ValveRunningBinarySensor(coordinator, valve["valve"]))

    for idx, _mv in enumerate(device.get("masterValves", [])):
        entities.append(MasterValveActiveBinarySensor(coordinator, idx))
    for idx, sensor in enumerate(device.get("sensors", [])):
        # Only surface sensors the controller reports as wired/active.
        if sensor.get("active"):
            entities.append(FlowSensorActiveBinarySensor(coordinator, idx))

    entities.append(SystemAutoWaterBinarySensor(coordinator))
    entities.append(JobRunningBinarySensor(coordinator))
    entities.append(ProblemBinarySensor(coordinator))

    async_add_entities(entities)


class _ZoneBase(IrrigreenEntity, BinarySensorEntity):
    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int, suffix: str) -> None:
        super().__init__(coordinator, f"zone{zone_num}_{suffix}")
        self._zone_num = zone_num

    def _zone(self) -> dict | None:
        for z in (self._dashboard or {}).get("enabled_zones", []):
            if z.get("zone") == self._zone_num:
                return z
        return None


class ZoneWateringBinarySensor(_ZoneBase):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: IrrigreenCoordinator, zone_num: int) -> None:
        super().__init__(coordinator, zone_num, "watering")

    @property
    def name(self) -> str:
        z = self._zone()
        label = z.get("name") if z else f"Zone {self._zone_num}"
        return f"{label} watering"

    @property
    def is_on(self) -> bool | None:
        z = self._zone()
        if z is None:
            return None
        return str(z.get("status", "off")).lower() != "off"


class ValveRunningBinarySensor(IrrigreenEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: IrrigreenCoordinator, valve_num: int) -> None:
        super().__init__(coordinator, f"valve{valve_num}_running")
        self._valve_num = valve_num
        self._attr_name = f"Valve {valve_num} running"

    @property
    def is_on(self) -> bool | None:
        for v in (self._dashboard or {}).get("enabled_valves", []):
            if v.get("valve") == self._valve_num:
                return str(v.get("status", "off")).lower() != "off"
        return None


class MasterValveActiveBinarySensor(IrrigreenEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: IrrigreenCoordinator, idx: int) -> None:
        super().__init__(coordinator, f"master_valve{idx + 1}_active")
        self._idx = idx
        self._attr_name = f"Master valve {idx + 1} active"

    @property
    def is_on(self) -> bool | None:
        mvs = (self._device_status or {}).get("masterValves", [])
        if self._idx < len(mvs):
            return bool(mvs[self._idx].get("active"))
        return None


class FlowSensorActiveBinarySensor(IrrigreenEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: IrrigreenCoordinator, idx: int) -> None:
        super().__init__(coordinator, f"sensor{idx + 1}_active")
        self._idx = idx
        self._attr_name = f"Sensor {idx + 1} active"

    @property
    def is_on(self) -> bool | None:
        sensors = (self._device_status or {}).get("sensors", [])
        if self._idx < len(sensors):
            return bool(sensors[self._idx].get("active"))
        return None


class SystemAutoWaterBinarySensor(IrrigreenEntity, BinarySensorEntity):
    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "system_auto_water")
        self._attr_name = "Automatic watering"

    @property
    def is_on(self) -> bool | None:
        d = self._dashboard
        if d is None:
            return None
        return bool(d.get("system_auto_water"))


class ProblemBinarySensor(IrrigreenEntity, BinarySensorEntity):
    """On when any head/valve reports an error (stuck valve, head fault, etc.)."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "problem")
        self._attr_name = "Problem"

    @property
    def is_on(self) -> bool | None:
        errs = self.coordinator.device_errors()
        count = (self.coordinator.system_dashboard or {}).get("error_count") or 0
        return bool(errs) or count > 0

    @property
    def extra_state_attributes(self):
        return {"errors": self.coordinator.device_errors()}


class JobRunningBinarySensor(IrrigreenEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: IrrigreenCoordinator) -> None:
        super().__init__(coordinator, "job_running")
        self._attr_name = "Job running"

    @property
    def is_on(self) -> bool | None:
        job = self._job
        if job is None:
            return None
        # A job is active while it has not completed/exited.
        return not (job.get("complete") or job.get("exit"))
