"""Sensors: activity, current/last game, drives, library, saves and dashboard."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .const import ACT_DASHBOARD, ACTIVITIES, CAT_APPS, CAT_GAMES
from .coordinator import XboxCoordinator
from .entity import XboxEntity, XboxXbmcEntity

# disk drives: C system, E data/saves, F/G extra, X/Y/Z game cache
DRIVE_KEYS = ["c", "e", "f", "g", "x", "y", "z"]


@dataclass(frozen=True, kw_only=True)
class XboxSensorDescription(SensorEntityDescription):
    value: Callable[[XboxCoordinator], Any]
    attrs: Callable[[XboxCoordinator], dict] | None = None


def _ts(value: float | None) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def _current(c: XboxCoordinator) -> dict | None:
    d = c.data or {}
    return d.get("current") if d.get("activity") != ACT_DASHBOARD else None


def _items(c: XboxCoordinator, cat: str) -> list[dict]:
    return sorted((i for i in c.library if i["category"] == cat), key=lambda i: i["name"].casefold())


SENSORS: list[XboxSensorDescription] = [
    XboxSensorDescription(
        key="activity",
        device_class=SensorDeviceClass.ENUM,
        options=ACTIVITIES,
        value=lambda c: (c.data or {}).get("activity"),
    ),
    XboxSensorDescription(
        key="current_game",
        value=lambda c: (_current(c) or {}).get("name"),
        attrs=lambda c: {
            "path": (_current(c) or {}).get("path"),
            "title_id": (_current(c) or {}).get("title_id"),
            "started": _ts((_current(c) or {}).get("started")),
            "launched_by_ha": (_current(c) or {}).get("by_ha"),
        },
    ),
    XboxSensorDescription(
        key="last_game",
        value=lambda c: (c.last or {}).get("name"),
        attrs=lambda c: {
            "path": (c.last or {}).get("path"),
            "title_id": (c.last or {}).get("title_id"),
            "started": _ts((c.last or {}).get("started")),
            "ended": _ts((c.last or {}).get("ended")),
        },
    ),
    XboxSensorDescription(
        key="last_session",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value=lambda c: (c.last or {}).get("minutes"),
    ),
    XboxSensorDescription(
        key="games",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value=lambda c: len(_items(c, CAT_GAMES)),
        attrs=lambda c: {"list": [i["name"] for i in _items(c, CAT_GAMES)]},
    ),
    XboxSensorDescription(
        key="apps",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="apps",
        value=lambda c: len(_items(c, CAT_APPS)),
        attrs=lambda c: {"list": [i["name"] for i in _items(c, CAT_APPS)]},
    ),
    XboxSensorDescription(
        key="saves",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="games",
        value=lambda c: sum(1 for s in c.saves if s["slots"]),
        attrs=lambda c: {s["name"]: s["slots"] for s in sorted(c.saves, key=lambda s: s["name"].casefold())},
    ),
    XboxSensorDescription(
        key="library_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c: _ts(c.library_at),
    ),
    XboxSensorDescription(
        key="dashboard",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c: (c.system or "").replace("UNIX emulated by ", "") or None,
        attrs=lambda c: {
            "path": c.dashboard_path,
            "network": c.config.get("network_type"),
            "fan_speed": c.config.get("fan_speed"),
            "dvd_autolaunch": c.config.get("dvd_launch"),
            "sntp_server": c.config.get("sntp_server"),
            "ftp_max_users": c.config.get("ftp_max_users"),
        },
    ),
]


@dataclass(frozen=True, kw_only=True)
class XbmcSensorDescription(SensorEntityDescription):
    field: str


XBMC_SENSORS = [
    XbmcSensorDescription(
        key="gpu_temperature",
        field="gpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    XbmcSensorDescription(
        key="cpu_temperature",
        field="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    XbmcSensorDescription(
        key="hdd_temperature",
        field="hdd_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    XbmcSensorDescription(
        key="fan_speed",
        field="fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    XbmcSensorDescription(
        key="free_memory",
        field="free_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XbmcSensorDescription(key="xbmc_window", field="window"),
    XbmcSensorDescription(key="xbmc_version", field="build", entity_category=EntityCategory.DIAGNOSTIC),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [XboxSensor(coordinator, d) for d in SENSORS]
    entities += [XbmcSensor(coordinator, d) for d in XBMC_SENSORS]
    for drive in DRIVE_KEYS:
        entities.append(XboxDriveSensor(coordinator, drive, "free"))
        entities.append(XboxDriveSensor(coordinator, drive, "usage"))
    async_add_entities(entities)


class XboxSensor(XboxEntity, SensorEntity):
    entity_description: XboxSensorDescription

    def __init__(self, coordinator: XboxCoordinator, description: XboxSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict | None:
        return self.entity_description.attrs(self.coordinator) if self.entity_description.attrs else None


class XboxDriveSensor(XboxEntity, SensorEntity):
    """Free space (GB) and usage (%) of each partition; keeps the last read value off the dashboard."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: XboxCoordinator, drive: str, kind: str) -> None:
        super().__init__(coordinator, f"{kind}_{drive}")
        self._drive = drive.upper()
        self._kind = kind
        if kind == "free":
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
            self._attr_suggested_display_precision = 2
        else:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_suggested_display_precision = 1
            self._attr_icon = "mdi:harddisk"
        if drive in ("x", "y", "z"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return super().available and self._drive in self.coordinator.drives

    @property
    def native_value(self) -> float | None:
        d = self.coordinator.drives.get(self._drive)
        if not d:
            return None
        if self._kind == "free":
            return round(d["free"] / 1024, 3)
        return round(100 * d["used"] / d["total"], 1)

    @property
    def extra_state_attributes(self) -> dict | None:
        d = self.coordinator.drives.get(self._drive)
        if not d:
            return None
        return {"used_gb": round(d["used"] / 1024, 2), "total_gb": round(d["total"] / 1024, 2)}


class XbmcSensor(XboxXbmcEntity, SensorEntity):
    """Telemetry only XBMC exposes (HTTP API, or the script on XBMC4Gamers). Keeps the last value."""

    entity_description: XbmcSensorDescription

    def __init__(self, coordinator: XboxCoordinator, description: XbmcSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._last: Any = None

    @property
    def available(self) -> bool:
        return XboxEntity.available.fget(self) and (self._telemetry.get(self.entity_description.field) is not None or self._last is not None)

    @property
    def _telemetry(self) -> dict:
        return self.data.get("telemetry") or {}

    @property
    def native_value(self) -> Any:
        value = self._telemetry.get(self.entity_description.field)
        if value is not None:
            self._last = value
        return self._last
