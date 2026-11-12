"""Image with the cover of the current game (or the last one played)."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import XboxConfigEntry
from .const import ACT_DASHBOARD
from .entity import XboxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([XboxCover(hass, entry.runtime_data)])


class XboxCover(XboxEntity, ImageEntity):
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        XboxEntity.__init__(self, coordinator, "cover")
        ImageEntity.__init__(self, hass)
        self._tid: str | None = None
        self._update_tid()

    def _pick(self) -> dict | None:
        data = self.coordinator.data or {}
        if data.get("activity") != ACT_DASHBOARD and data.get("current"):
            return data["current"]
        return self.coordinator.last

    def _update_tid(self) -> None:
        item = self._pick() or {}
        tid = item.get("title_id")
        if tid != self._tid:
            self._tid = tid
            self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_tid()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict:
        item = self._pick() or {}
        return {"game": item.get("name"), "title_id": self._tid}

    async def async_image(self) -> bytes | None:
        item = self._pick() or {}
        png = await self.coordinator.async_cover(self._tid, item.get("path"))
        if png is None:  # no cover: Xbox logo instead of a 500 error in the proxy
            png = await self.hass.async_add_executor_job(_fallback)
        return png


def _fallback() -> bytes:
    with open(Path(__file__).parent / "brand" / "icon.png", "rb") as f:
        return f.read()
