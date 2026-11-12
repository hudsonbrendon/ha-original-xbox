"""Config.xml numbers: screensaver wait and auto turn-off."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XboxError
from .entity import XboxDashboardEntity

# key -> (min, max, step, unit)
NUMBERS = {
    "screensaver_wait": (0, 3600, 10, UnitOfTime.SECONDS),
    "auto_turn_off": (0, 600, 5, UnitOfTime.MINUTES),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(XboxConfigNumber(entry.runtime_data, key) for key in NUMBERS)


class XboxConfigNumber(XboxDashboardEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, key)
        lo, hi, step, unit = NUMBERS[key]
        self._attr_native_min_value = lo
        self._attr_native_max_value = hi
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self) -> bool:
        return super().available and self._attr_translation_key in self.coordinator.config

    @property
    def native_value(self) -> float | None:
        return self.coordinator.config.get(self._attr_translation_key)

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.async_set_config(self._attr_translation_key, int(value))
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
