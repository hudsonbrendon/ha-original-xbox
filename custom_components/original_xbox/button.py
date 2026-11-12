"""Buttons: power, tray, network/FTP, dashboards, backup and library."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry, async_backup_saves
from .api import XboxError
from .const import MS_DASHBOARD
from .entity import XboxControlEntity, XboxDashboardEntity

# key -> (SITE command, drops the connection?, category)
SITE_BUTTONS = {
    # UnleashX 0.37 REBOOT calls XLaunchNewImage(NULL) and fails silently; POWERCYCLE really restarts
    "restart": ("POWERCYCLE", True, None),
    "shut_down": ("SHUTDOWN", True, None),
    "open_tray": ("TRAYOPEN", False, None),
    "close_tray": ("TRAYCLOSE", False, None),
    "restart_network": ("NETRESET", True, EntityCategory.DIAGNOSTIC),
    "restart_ftp": ("FTPRESET", True, EntityCategory.DIAGNOSTIC),
}
OTHER_BUTTONS = ["reload_dashboard", "microsoft_dashboard", "backup_saves", "refresh_library"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        (XboxPowerButton if key in POWER_KEYS else XboxButton)(coordinator, key)
        for key in [*SITE_BUTTONS, *OTHER_BUTTONS]
    )


POWER_KEYS = {"restart", "shut_down", "reload_dashboard", "microsoft_dashboard"}


class XboxButton(XboxDashboardEntity, ButtonEntity):
    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, key)
        if key == "restart":
            self._attr_device_class = ButtonDeviceClass.RESTART
        if key in SITE_BUTTONS:
            self._attr_entity_category = SITE_BUTTONS[key][2]
        elif key in ("backup_saves", "refresh_library", "reload_dashboard"):
            self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        key = self._attr_translation_key
        c = self.coordinator
        try:
            if key in ("restart", "shut_down"):
                await c.async_power(SITE_BUTTONS[key][0])
            elif key in SITE_BUTTONS:
                command, fire, _ = SITE_BUTTONS[key]
                await c.async_site(command, fire=fire)
            elif key == "reload_dashboard":
                await c.async_launch(c.dashboard_path)
            elif key == "microsoft_dashboard":
                await c.async_launch(MS_DASHBOARD)
            elif key == "backup_saves":
                await async_backup_saves(self.hass, c)
            elif key == "refresh_library":
                c.async_start_scan()
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        await c.async_request_refresh()


class XboxPowerButton(XboxControlEntity, XboxButton):
    """Power and dashboard switching also work from XBMC."""
