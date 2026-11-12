"""Original Xbox: a softmodded/modchipped Xbox in Home Assistant over the dashboard FTP."""

from __future__ import annotations

import io
import os
import time
import zipfile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .api import XboxClient, XboxError, to_xbox_path
from .const import DEFAULT_PASSWORD, DEFAULT_USERNAME, DOMAIN
from .coordinator import XboxCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type XboxConfigEntry = ConfigEntry[XboxCoordinator]

ATTR_ENTRY = "config_entry_id"
SCHEMA_BASE = {vol.Optional(ATTR_ENTRY): cv.string}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    client = XboxClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
        entry.data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
    )
    coordinator = XboxCoordinator(hass, entry, client)
    await coordinator.async_load()
    # the Xbox is mostly off or in a game: do not fail setup because of that
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> XboxCoordinator:
    entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN)]
    if entry_id := call.data.get(ATTR_ENTRY):
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError("no Original Xbox configured")
    return entries[0].runtime_data


async def async_backup_saves(hass: HomeAssistant, coordinator: XboxCoordinator) -> str:
    r"""Download all of E:\UDATA to /config/backups/original_xbox/saves-YYYYMMDD-HHMM.zip."""
    folder = hass.config.path("backups", DOMAIN)
    path = os.path.join(folder, time.strftime("saves-%Y%m%d-%H%M.zip"))

    def run() -> int:
        os.makedirs(folder, exist_ok=True)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            count = coordinator.client.download_tree("E:\\UDATA", lambda rel, data: zf.writestr(f"UDATA/{rel}", data))
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        return count

    try:
        count = await hass.async_add_executor_job(run)
    except XboxError as err:
        raise HomeAssistantError(f"saves backup failed: {err}") from err
    return f"{path} ({count} files)"


def _register_services(hass: HomeAssistant) -> None:
    async def launch(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        target = call.data["path"]
        item = coordinator.find_item(target)
        try:
            await coordinator.async_launch(item["path"] if item else to_xbox_path(target))
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err

    async def site_command(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            reply = await coordinator.async_site(call.data["command"], fire=False)
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"reply": reply}

    async def upload_file(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        source = call.data["source"]
        if not hass.config.is_allowed_path(source):
            raise ServiceValidationError(f"{source} is not in allowlist_external_dirs")
        destination = call.data["destination"]

        def run() -> None:
            with open(source, "rb") as f:
                data = f.read()
            if destination.endswith(("\\", "/")):
                target = destination + os.path.basename(source)
            else:
                target = destination
            coordinator.client.mkdirs(target.replace("/", "\\").rsplit("\\", 1)[0])
            coordinator.client.write(target, data)

        try:
            await hass.async_add_executor_job(run)
        except (OSError, XboxError) as err:
            raise HomeAssistantError(f"upload failed: {err}") from err

    async def upload_folder(call: ServiceCall) -> ServiceResponse:
        r"""Copy a folder from HA to the Xbox (e.g. a game to F:\Games\Name) and refresh the library."""
        coordinator = _coordinator(hass, call)
        source = call.data["source"].rstrip("/")
        if not hass.config.is_allowed_path(source) or not await hass.async_add_executor_job(os.path.isdir, source):
            raise ServiceValidationError(f"{source} is not a folder in allowlist_external_dirs")
        destination = call.data.get("destination") or f"F:\\Games\\{os.path.basename(source)}"
        if coordinator.data and coordinator.data.get("activity") != "dashboard":
            raise HomeAssistantError("the Xbox must be on the dashboard (UnleashX) to receive files")
        try:
            files, total, skipped = await hass.async_add_executor_job(
                coordinator.client.upload_tree, source, destination
            )
        except (OSError, XboxError) as err:
            raise HomeAssistantError(f"folder upload failed: {err}") from err
        coordinator.async_start_scan()
        return {"destination": destination, "files": files, "bytes": total, "skipped": skipped}

    async def download_file(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        destination = call.data["destination"]
        if not hass.config.is_allowed_path(destination):
            raise ServiceValidationError(f"{destination} is not in allowlist_external_dirs")
        try:
            data = await hass.async_add_executor_job(coordinator.client.read, call.data["source"])
        except XboxError as err:
            raise HomeAssistantError(f"download failed: {err}") from err

        def save() -> None:
            os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
            with open(destination, "wb") as f:
                f.write(data)

        await hass.async_add_executor_job(save)
        return {"file": destination, "bytes": len(data)}

    async def list_folder(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            entries = await hass.async_add_executor_job(coordinator.client.listdir, call.data["path"])
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"items": [{"name": e.name, "is_dir": e.is_dir, "size": e.size} for e in entries]}

    async def xbmc_command(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            reply = await coordinator.async_xbmc(call.data["command"], call.data.get("parameter"))
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"reply": reply}

    async def backup_saves(call: ServiceCall) -> ServiceResponse:
        return {"file": await async_backup_saves(hass, _coordinator(hass, call))}

    async def refresh_library(call: ServiceCall) -> None:
        _coordinator(hass, call).async_start_scan()

    reg = hass.services.async_register
    reg(DOMAIN, "launch", launch, vol.Schema({**SCHEMA_BASE, vol.Required("path"): cv.string}))
    reg(
        DOMAIN,
        "site_command",
        site_command,
        vol.Schema({**SCHEMA_BASE, vol.Required("command"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    reg(
        DOMAIN,
        "upload_file",
        upload_file,
        vol.Schema({**SCHEMA_BASE, vol.Required("source"): cv.string, vol.Required("destination"): cv.string}),
    )
    reg(
        DOMAIN,
        "upload_folder",
        upload_folder,
        vol.Schema({**SCHEMA_BASE, vol.Required("source"): cv.string, vol.Optional("destination"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        "download_file",
        download_file,
        vol.Schema({**SCHEMA_BASE, vol.Required("source"): cv.string, vol.Required("destination"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        "list_folder",
        list_folder,
        vol.Schema({**SCHEMA_BASE, vol.Required("path"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    reg(
        DOMAIN,
        "xbmc_command",
        xbmc_command,
        vol.Schema({**SCHEMA_BASE, vol.Required("command"): cv.string, vol.Optional("parameter"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(DOMAIN, "backup_saves", backup_saves, vol.Schema(SCHEMA_BASE), supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "refresh_library", refresh_library, vol.Schema(SCHEMA_BASE))
