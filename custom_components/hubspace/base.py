from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .hubspace import HubspaceRawDevice


class HubspaceEntity(CoordinatorEntity):
    hubspace_device: HubspaceRawDevice

    def __init__(self, idx: str, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(coordinator=coordinator, context=idx)
        self._idx = idx
        self.hubspace_device = coordinator.data[self._idx]

        self._attr_unique_id = self.hubspace_device.unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.hubspace_device.deviceId),
            },
            name=self.hubspace_device.friendlyName,
            manufacturer=self.hubspace_device.manufacturer,
            model=self.hubspace_device.model,
        )
        # Parse the initial device data
        self._handle_coordinator_update()
