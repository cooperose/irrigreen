"""Shared entity base for Irrigreen."""
from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IrrigreenCoordinator


class IrrigreenEntity(CoordinatorEntity[IrrigreenCoordinator]):
    """Base entity tying everything to one controller device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IrrigreenCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.host}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name=self.coordinator.entry.title,
            manufacturer="Irrigreen",
            model="Sprinkler Controller",
            configuration_url=f"http://{self.coordinator.host}",
        )

    @property
    def _dashboard(self) -> dict | None:
        return (self.coordinator.data or {}).get("dashboard")

    @property
    def _device_status(self) -> dict | None:
        return (self.coordinator.data or {}).get("device_status")

    @property
    def _job(self) -> dict | None:
        return (self.coordinator.data or {}).get("job_status")

    @property
    def _schedules(self) -> list | None:
        data = (self.coordinator.data or {}).get("schedules")
        if isinstance(data, dict):
            return data.get("schedules")
        return None
