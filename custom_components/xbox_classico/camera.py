"""Câmera: screenshot da tela do Xbox (TakeScreenshot da HTTP API do XBMC)."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XboxError
from .const import LOGGER
from .entity import XboxXbmcEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([XboxScreen(entry.runtime_data)])


class XboxScreen(XboxXbmcEntity, Camera):
    _attr_frame_interval = 10

    def __init__(self, coordinator) -> None:
        XboxXbmcEntity.__init__(self, coordinator, "tela")
        Camera.__init__(self)
        self._last: bytes | None = None

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        if self.data.get("xbmc") is None:
            return self._last
        try:
            self._last = await self.hass.async_add_executor_job(self.coordinator.xbmc.screenshot, 640)
        except XboxError as err:
            LOGGER.debug("screenshot falhou: %s", err)
        return self._last
