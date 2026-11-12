"""Downloadable diagnostics: state, drives, dashboard config and library (no password)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import XboxConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: XboxConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    data = {k: v for k, v in (c.data or {}).items() if k != "at"}
    return {
        "entry": async_redact_data({**entry.data, **entry.options}, {CONF_PASSWORD}),
        "system": c.system,
        "state": data,
        "drives": c.drives,
        "config": c.config,
        "library": c.library,
        "saves": c.saves,
        "library_at": c.library_at,
    }
