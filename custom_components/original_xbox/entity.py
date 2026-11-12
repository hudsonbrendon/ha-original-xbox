"""Base entity for the Original Xbox integration."""

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
            model=f"Xbox {coordinator.console_info['xbox_version']}"
            if coordinator.console_info.get("xbox_version")
            else "Xbox (original)",
            hw_version=coordinator.console_info.get("bios"),
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
    """Commands only UnleashX understands: available with the console on the dashboard."""

    @property
    def available(self) -> bool:
        return super().available and self.in_dashboard


class XboxControlEntity(XboxEntity):
    """Available in UnleashX or XBMC (HTTP API or, without it, the XBMC FTP SITE command)."""

    @property
    def available(self) -> bool:
        # call the base directly: in the buttons MRO the next one would be XboxDashboardEntity
        if not XboxEntity.available.fget(self):
            return False
        # in XBMC it works with or without the web server: without it, commands go via the XBMC FTP SITE
        return self.in_dashboard or (self.data.get("activity") == ACT_XBMC and bool(self.data.get("online")))


class XboxXbmcEntity(XboxEntity):
    """Only with XBMC running and the HTTP API answering."""

    @property
    def xbmc(self) -> dict:
        return self.data.get("xbmc") or {}

    @property
    def available(self) -> bool:
        return super().available and self.data.get("xbmc") is not None
