"""Switches que editam o Config.xml do UnleashX (com backup e recarga do dashboard)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XboxError
from .entity import XboxDashboardEntity

KEYS = [
    "sntp",
    "autolaunch_games",
    "autolaunch_dvd",
    "autolaunch_audiocd",
    "autolaunch_data",
    "newsfeed",
    "widescreen",
    "use_1080i",
    "fahrenheit",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(XboxConfigSwitch(entry.runtime_data, key) for key in KEYS)


class XboxConfigSwitch(XboxDashboardEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        return super().available and self._attr_translation_key in self.coordinator.config

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.config.get(self._attr_translation_key)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        try:
            await self.coordinator.async_set_config(self._attr_translation_key, value)
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
