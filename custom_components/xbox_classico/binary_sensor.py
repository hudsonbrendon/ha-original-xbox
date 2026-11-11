"""Sensores binários: dashboard no ar (FTP) e console na rede (ping)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .entity import XboxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities([XboxBinary(c, "ftp", "online"), XboxBinary(c, "rede", "ping")])


class XboxBinary(XboxEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, key: str, field: str) -> None:
        super().__init__(coordinator, key)
        self._field = field
        if key == "rede":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return bool(self.data.get(self._field))

    @property
    def extra_state_attributes(self) -> dict | None:
        if self._field == "online":
            return {"banner": self.data.get("banner"), "host": self.coordinator.client.host}
        return None
