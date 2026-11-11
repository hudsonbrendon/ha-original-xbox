"""Selects para abrir um jogo ou aplicativo direto do dashboard."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XboxError
from .const import ACT_DASHBOARD, CAT_APPS, CAT_GAMES
from .entity import XboxControlEntity

KEYS = {"abrir_jogo": CAT_GAMES, "abrir_aplicativo": CAT_APPS}


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(XboxLaunchSelect(entry.runtime_data, key) for key in KEYS)


class XboxLaunchSelect(XboxControlEntity, SelectEntity):
    @property
    def _items(self) -> list[dict]:
        cat = KEYS[self._attr_translation_key]
        return sorted((i for i in self.coordinator.library if i["category"] == cat), key=lambda i: i["name"].casefold())

    @property
    def options(self) -> list[str]:
        return list(dict.fromkeys(i["name"] for i in self._items))

    @property
    def current_option(self) -> str | None:
        cur = self.data.get("current")
        if not cur or self.data.get("activity") == ACT_DASHBOARD:
            return None
        return cur["name"] if cur["name"] in self.options else None

    async def async_select_option(self, option: str) -> None:
        item = next((i for i in self._items if i["name"] == option), None)
        if item is None:
            raise HomeAssistantError(f"não está na biblioteca: {option}")
        try:
            await self.coordinator.async_launch(item["path"])
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
