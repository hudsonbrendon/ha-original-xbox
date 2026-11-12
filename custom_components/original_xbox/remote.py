"""Remote: Xbox controller buttons sent through the XBMC HTTP API."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XBMC_KEYS, XboxError
from .entity import XboxXbmcEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([XboxRemote(entry.runtime_data, "controller")])


class XboxRemote(XboxXbmcEntity, RemoteEntity):
    @property
    def is_on(self) -> bool:
        return self.available

    @property
    def extra_state_attributes(self) -> dict:
        return {"commands": sorted(XBMC_KEYS)}

    async def async_send_command(self, command: Iterable[str], **kwargs) -> None:
        repeats = int(kwargs.get("num_repeats", 1))
        delay = float(kwargs.get("delay_secs", 0.3))
        for _ in range(repeats):
            for cmd in command:
                if cmd.lower() not in XBMC_KEYS and not str(cmd).isdigit():
                    raise HomeAssistantError(f"unknown command: {cmd} (use {', '.join(sorted(XBMC_KEYS))})")
                try:
                    await self.hass.async_add_executor_job(self.coordinator.xbmc.send_key, cmd)
                except XboxError as err:
                    raise HomeAssistantError(str(err)) from err
                await asyncio.sleep(delay)
        await self.coordinator.async_request_refresh()
