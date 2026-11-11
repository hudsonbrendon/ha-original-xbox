"""Entidade base do Xbox Clássico."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ACT_DASHBOARD, ACT_XBMC, DOMAIN
from .coordinator import XboxCoordinator


class XboxEntity(CoordinatorEntity[XboxCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: XboxCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        system = coordinator.system or ""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer="Microsoft",
            model="Xbox (original)",
            name=entry.title,
            sw_version=system.replace("UNIX emulated by ", "") or None,
        )

    @property
    def data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def in_dashboard(self) -> bool:
        return self.data.get("activity") == ACT_DASHBOARD


class XboxDashboardEntity(XboxEntity):
    """Comandos que só o UnleashX entende: disponíveis com o console no dashboard."""

    @property
    def available(self) -> bool:
        return super().available and self.in_dashboard


class XboxControlEntity(XboxEntity):
    """Disponível no UnleashX ou no XBMC (HTTP API ou, sem ela, SITE do FTP do XBMC)."""

    @property
    def available(self) -> bool:
        # chama a base direto: no MRO dos botões o próximo seria XboxDashboardEntity
        if not XboxEntity.available.fget(self):
            return False
        # no XBMC vale com ou sem servidor web: sem ele, os comandos vão pelo SITE do FTP do XBMC
        return self.in_dashboard or (self.data.get("activity") == ACT_XBMC and bool(self.data.get("online")))


class XboxXbmcEntity(XboxEntity):
    """Só com o XBMC aberto e a HTTP API respondendo."""

    @property
    def xbmc(self) -> dict:
        return self.data.get("xbmc") or {}

    @property
    def available(self) -> bool:
        return super().available and self.data.get("xbmc") is not None
