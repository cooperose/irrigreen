"""Sensors for Irrigreen (water adjustments, current, schedules, job detail)."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfElectricCurrent
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
    schedules = (data.get("schedules") or {}).get("schedules", []) if isinstance(
        data.get("schedules"), dict
    ) else []

    entities: list[SensorEntity] = [
        SystemWaterAdjSensor(coordinator),
        JobStatusSensor(coordinator),
        FirmwareVersionSensor(coordinator),
        ConnectionSensor(coordinator),
        ActiveErrorsSensor(coordinator),
        LastRunWaterSensor(coordinator),
    ]

    entities.append(WeatherAdjustSensor(coordinator))

    for zone in dashboard.get("enabled_zones", []):
        entities.append(ZoneStatusSensor(coordinator, zone["zone"]))
        entities.append(ZoneWaterAdjSensor(coordinator, zone["zone"]))
        entities.append(ZoneTypeSensor(coordinator, zone["zone"]))

    for idx, _mv in enumerate(device.get("masterValves", [])):
        entities.append(MasterValveCurrentSensor(coordinator, idx))

    for idx, sensor in enumerate(device.get("sensors", [])):
        if sensor.get("active"):
            entities.append(FlowSensorPulsesSensor(coordinator, idx))

    for sched in schedules:
        if not sched.get("deleted"):
            entities.append(ScheduleSensor(coordinator, sched["name"]))

    async_add_entities(entities)


class _ZoneMixin(IrrigreenEntity):
    def __init__(self, coordinator, zone_num, suffix):
        super().__init__(coordinator, f"zone{zone_num}_{suffix}")
        self._zone_num = zone_num

    def _zone(self) -> dict | None:
        for z in (self._dashboard or {}).get("enabled_zones", []):
            if z.get("zone") == self._zone_num:
                return z
        return None

    def _zone_label(self) -> str:
        z = self._zone()
        return z.get("name") if z else f"Zone {self._zone_num}"


class ZoneStatusSensor(_ZoneMixin, SensorEntity):
    def __init__(self, coordinator, zone_num):
        super().__init__(coordinator, zone_num, "status")

    @property
    def name(self) -> str:
        return f"{self._zone_label()} status"

    @property
    def native_value(self):
        z = self._zone()
        return z.get("status") if z else None

    @property
    def extra_state_attributes(self):
        z = self._zone()
        if not z:
            return None
        return {"zone": z.get("zone"), "schedule_revs": z.get("schedule_revs")}


class ZoneWaterAdjSensor(_ZoneMixin, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, zone_num):
        super().__init__(coordinator, zone_num, "water_adj")

    @property
    def name(self) -> str:
        return f"{self._zone_label()} water adjustment"

    @property
    def native_value(self):
        z = self._zone()
        if not z or z.get("water_adj") is None:
            return None
        return round(float(z["water_adj"]) * 100)


class ZoneTypeSensor(_ZoneMixin, SensorEntity):
    """Head model (XR / HydroBoost) plus its config as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator, zone_num):
        super().__init__(coordinator, zone_num, "type")

    @property
    def name(self) -> str:
        return f"{self._zone_label()} type"

    @property
    def native_value(self):
        return self.coordinator.zone_type(self._zone_num)

    @property
    def extra_state_attributes(self):
        pref = self.coordinator.sprinkler_pref(self._zone_num)
        summary = self.coordinator.zone_summary(self._zone_num)
        aw = pref.get("aw") or {}
        zt = aw.get("zoneTypes") or {}
        return {
            "double_coverage": pref.get("doubleCoverage"),
            "flow_restrictor": pref.get("hasFlowRestrictor"),
            "xp_enabled": pref.get("xpEnabled"),
            "plant": zt.get("plant"),
            "soil": zt.get("soil"),
            "sun": zt.get("sun"),
            "calibrated": summary.get("calibrated") if "calibrated" in summary else None,
            "sqft": summary.get("sqft"),
            "head_id": (self.coordinator.zone_desc(self._zone_num) or {}).get("id"),
        }


class WeatherAdjustSensor(IrrigreenEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:weather-partly-rainy"

    def __init__(self, coordinator):
        super().__init__(coordinator, "weather_adjust")
        self._attr_name = "Weather adjustment"

    @property
    def native_value(self):
        wa = (self.coordinator.system_info.get("controller") or {}).get("weather_adjust")
        try:
            return round(float(wa) * 100)
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self):
        ctrl = self.coordinator.system_info.get("controller") or {}
        return {
            "automatic_watering": self.coordinator.system_pref.get("awEnabled"),
            "timezone": ctrl.get("timezone"),
            "eto_days": ctrl.get("eto_days"),
            "battery": ctrl.get("battery"),
        }


class SystemWaterAdjSensor(IrrigreenEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator, "system_water_adj")
        self._attr_name = "System water adjustment"

    @property
    def native_value(self):
        d = self._dashboard
        if d is None or d.get("system_water_adj") is None:
            return None
        return round(float(d["system_water_adj"]) * 100)


class MasterValveCurrentSensor(IrrigreenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, idx):
        super().__init__(coordinator, f"master_valve{idx + 1}_current")
        self._idx = idx
        self._attr_name = f"Master valve {idx + 1} current"

    @property
    def native_value(self):
        mvs = (self._device_status or {}).get("masterValves", [])
        if self._idx < len(mvs):
            return mvs[self._idx].get("current")
        return None

    @property
    def extra_state_attributes(self):
        mvs = (self._device_status or {}).get("masterValves", [])
        if self._idx < len(mvs):
            return {"peak_current": mvs[self._idx].get("peakCurrent")}
        return None


class FlowSensorPulsesSensor(IrrigreenEntity, SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, idx):
        super().__init__(coordinator, f"sensor{idx + 1}_pulses")
        self._idx = idx
        self._attr_name = f"Sensor {idx + 1} pulses"

    @property
    def native_value(self):
        sensors = (self._device_status or {}).get("sensors", [])
        if self._idx < len(sensors):
            return sensors[self._idx].get("pulses")
        return None


class ScheduleSensor(IrrigreenEntity, SensorEntity):
    def __init__(self, coordinator, name):
        super().__init__(coordinator, f"schedule_{name}")
        self._sched_name = name

    @property
    def name(self):
        return self.coordinator.schedule_display_name(self._sched_name)

    def _sched(self) -> dict | None:
        for s in (self._schedules or []):
            if s.get("name") == self._sched_name:
                return s
        return None

    @property
    def native_value(self):
        s = self._sched()
        if s is None:
            return None
        if s.get("watering"):
            return "watering"
        return "enabled" if s.get("enabled") else "disabled"

    @property
    def extra_state_attributes(self):
        s = self._sched()
        if s is None:
            return None
        return {
            "type": s.get("type"),
            "start_time": s.get("start_time"),
            "duration": s.get("duration"),
            "cycle": s.get("cycle"),
            "interval": s.get("interval"),
            "last_watering": s.get("last_watering"),
        }


class FirmwareVersionSensor(IrrigreenEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "firmware_version")
        self._attr_name = "Firmware version"

    @property
    def native_value(self):
        return (self.coordinator.system_info.get("controller") or {}).get("version")


class ConnectionSensor(IrrigreenEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator, "cloud_connection")
        self._attr_name = "Cloud connection"

    @property
    def native_value(self):
        return self.coordinator.connection.get("state")

    @property
    def extra_state_attributes(self):
        c = self.coordinator.connection
        return {"network": c.get("network"), "rssi": c.get("rssi")}


class ActiveErrorsSensor(IrrigreenEntity, SensorEntity):
    """Number of devices reporting an error, with details (stuck valves etc.)."""

    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator):
        super().__init__(coordinator, "active_errors")
        self._attr_name = "Active errors"

    @property
    def native_value(self):
        return len(self.coordinator.device_errors())

    @property
    def extra_state_attributes(self):
        errs = self.coordinator.device_errors()
        return {
            "error_count": (self.coordinator.system_dashboard or {}).get("error_count"),
            "errors": errs,
        }


class LastRunWaterSensor(IrrigreenEntity, SensorEntity):
    _attr_native_unit_of_measurement = "gal"
    _attr_icon = "mdi:water"

    def __init__(self, coordinator):
        super().__init__(coordinator, "last_run_water")
        self._attr_name = "Last run water use"

    def _last_run(self) -> dict:
        return (self.coordinator.system_dashboard or {}).get("last_run") or {}

    @property
    def native_value(self):
        return (self._last_run().get("actual") or {}).get("gallons")

    @property
    def extra_state_attributes(self):
        lr = self._last_run()
        sd = self.coordinator.system_dashboard or {}
        return {
            "schedule": lr.get("schedule"),
            "timestamp": lr.get("time_stamp"),
            "watering_history_days": sd.get("watering_history_days"),
            "watering_history_weeks": sd.get("watering_history_weeks"),
        }


class JobStatusSensor(IrrigreenEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "job_status")
        self._attr_name = "Current job"

    @property
    def native_value(self):
        job = self._job
        if job is None:
            return None
        if job.get("complete") or job.get("exit"):
            return "idle"
        return job.get("type") or "running"

    @property
    def extra_state_attributes(self):
        job = self._job
        if job is None:
            return None
        data = job.get("data") or {}

        def ts(value):
            try:
                return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                return None

        return {
            "type": job.get("type"),
            "complete": job.get("complete"),
            "start_time": ts(job.get("startTime")),
            "end_time": ts(job.get("endTime")),
            "start_reason": data.get("startReason"),
            "stop_reason": data.get("stopReason"),
            "status": data.get("status"),
            "uuid": job.get("uuid"),
        }
