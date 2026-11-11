"""Botões: energia, bandeja, rede/FTP, dashboards, backup e biblioteca."""

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

# chave -> (comando SITE, derruba a conexão?, categoria)
SITE_BUTTONS = {
    "reiniciar": ("REBOOT", True, None),
    "desligar": ("SHUTDOWN", True, None),
    "reinicio_completo": ("POWERCYCLE", True, EntityCategory.CONFIG),
    "abrir_bandeja": ("TRAYOPEN", False, None),
    "fechar_bandeja": ("TRAYCLOSE", False, None),
    "reiniciar_rede": ("NETRESET", True, EntityCategory.DIAGNOSTIC),
    "reiniciar_ftp": ("FTPRESET", True, EntityCategory.DIAGNOSTIC),
}
OTHER_BUTTONS = ["recarregar_dashboard", "dashboard_microsoft", "backup_saves", "atualizar_biblioteca"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        (XboxPowerButton if key in POWER_KEYS else XboxButton)(coordinator, key)
        for key in [*SITE_BUTTONS, *OTHER_BUTTONS]
    )


POWER_KEYS = {"reiniciar", "desligar", "reinicio_completo", "recarregar_dashboard", "dashboard_microsoft"}


class XboxButton(XboxDashboardEntity, ButtonEntity):
    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator, key)
        if key in ("reiniciar", "reinicio_completo"):
            self._attr_device_class = ButtonDeviceClass.RESTART
        if key in SITE_BUTTONS:
            self._attr_entity_category = SITE_BUTTONS[key][2]
        elif key in ("backup_saves", "atualizar_biblioteca", "recarregar_dashboard"):
            self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        key = self._attr_translation_key
        c = self.coordinator
        try:
            if key in ("reiniciar", "desligar", "reinicio_completo"):
                await c.async_power(SITE_BUTTONS[key][0])
            elif key in SITE_BUTTONS:
                command, fire, _ = SITE_BUTTONS[key]
                await c.async_site(command, fire=fire)
            elif key == "recarregar_dashboard":
                await c.async_launch(c.dashboard_path)
            elif key == "dashboard_microsoft":
                await c.async_launch(MS_DASHBOARD)
            elif key == "backup_saves":
                await async_backup_saves(self.hass, c)
            elif key == "atualizar_biblioteca":
                c.async_start_scan()
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        await c.async_request_refresh()


class XboxPowerButton(XboxControlEntity, XboxButton):
    """Energia e troca de dashboard funcionam também a partir do XBMC."""
