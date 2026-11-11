"""Xbox Clássico: Xbox original desbloqueado no Home Assistant pelo FTP do dashboard."""

from __future__ import annotations

import io
import os
import time
import zipfile

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

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
    # o Xbox passa a maior parte do tempo desligado ou em jogo: não falhar o setup por isso
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
        raise ServiceValidationError("nenhum Xbox Clássico configurado")
    return entries[0].runtime_data


async def async_backup_saves(hass: HomeAssistant, coordinator: XboxCoordinator) -> str:
    """Baixa E:\\UDATA inteiro para /config/backups/xbox_classico/saves-AAAAMMDD-HHMM.zip."""
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
        raise HomeAssistantError(f"backup dos saves falhou: {err}") from err
    return f"{path} ({count} arquivos)"


def _register_services(hass: HomeAssistant) -> None:
    async def executar(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        target = call.data["caminho"]
        item = coordinator.find_item(target)
        try:
            await coordinator.async_launch(item["path"] if item else to_xbox_path(target))
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err

    async def comando_site(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            reply = await coordinator.async_site(call.data["comando"], fire=False)
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"resposta": reply}

    async def enviar_arquivo(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        origem = call.data["origem"]
        if not hass.config.is_allowed_path(origem):
            raise ServiceValidationError(f"{origem} não está em allowlist_external_dirs")
        destino = call.data["destino"]

        def run() -> None:
            with open(origem, "rb") as f:
                data = f.read()
            if destino.endswith(("\\", "/")):
                target = destino + os.path.basename(origem)
            else:
                target = destino
            coordinator.client.mkdirs(target.replace("/", "\\").rsplit("\\", 1)[0])
            coordinator.client.write(target, data)

        try:
            await hass.async_add_executor_job(run)
        except (OSError, XboxError) as err:
            raise HomeAssistantError(f"envio falhou: {err}") from err

    async def enviar_pasta(call: ServiceCall) -> ServiceResponse:
        """Copia uma pasta do HA para o Xbox (ex.: um jogo para F:\\Games\\Nome) e atualiza a biblioteca."""
        coordinator = _coordinator(hass, call)
        origem = call.data["origem"].rstrip("/")
        if not hass.config.is_allowed_path(origem) or not os.path.isdir(origem):
            raise ServiceValidationError(f"{origem} não é uma pasta em allowlist_external_dirs")
        destino = call.data.get("destino") or f"F:\\Games\\{os.path.basename(origem)}"
        if coordinator.data and coordinator.data.get("activity") != "dashboard":
            raise HomeAssistantError("o Xbox precisa estar no dashboard (UnleashX) para receber arquivos")
        try:
            files, total, skipped = await hass.async_add_executor_job(coordinator.client.upload_tree, origem, destino)
        except (OSError, XboxError) as err:
            raise HomeAssistantError(f"envio da pasta falhou: {err}") from err
        coordinator.async_start_scan()
        return {"destino": destino, "arquivos": files, "bytes": total, "ignorados": skipped}

    async def baixar_arquivo(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        destino = call.data["destino"]
        if not hass.config.is_allowed_path(destino):
            raise ServiceValidationError(f"{destino} não está em allowlist_external_dirs")
        try:
            data = await hass.async_add_executor_job(coordinator.client.read, call.data["origem"])
        except XboxError as err:
            raise HomeAssistantError(f"download falhou: {err}") from err

        def save() -> None:
            os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
            with open(destino, "wb") as f:
                f.write(data)

        await hass.async_add_executor_job(save)
        return {"arquivo": destino, "bytes": len(data)}

    async def listar(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            entries = await hass.async_add_executor_job(coordinator.client.listdir, call.data["caminho"])
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"itens": [{"nome": e.name, "pasta": e.is_dir, "bytes": e.size} for e in entries]}

    async def xbmc_comando(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            reply = await coordinator.async_xbmc(call.data["comando"], call.data.get("parametro"))
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        return {"resposta": reply}

    async def backup_saves(call: ServiceCall) -> ServiceResponse:
        return {"arquivo": await async_backup_saves(hass, _coordinator(hass, call))}

    async def atualizar_biblioteca(call: ServiceCall) -> None:
        _coordinator(hass, call).async_start_scan()

    reg = hass.services.async_register
    reg(DOMAIN, "executar", executar, vol.Schema({**SCHEMA_BASE, vol.Required("caminho"): cv.string}))
    reg(
        DOMAIN,
        "comando_site",
        comando_site,
        vol.Schema({**SCHEMA_BASE, vol.Required("comando"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    reg(
        DOMAIN,
        "enviar_arquivo",
        enviar_arquivo,
        vol.Schema({**SCHEMA_BASE, vol.Required("origem"): cv.string, vol.Required("destino"): cv.string}),
    )
    reg(
        DOMAIN,
        "enviar_pasta",
        enviar_pasta,
        vol.Schema({**SCHEMA_BASE, vol.Required("origem"): cv.string, vol.Optional("destino"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        "baixar_arquivo",
        baixar_arquivo,
        vol.Schema({**SCHEMA_BASE, vol.Required("origem"): cv.string, vol.Required("destino"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(
        DOMAIN,
        "listar",
        listar,
        vol.Schema({**SCHEMA_BASE, vol.Required("caminho"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    reg(
        DOMAIN,
        "xbmc_comando",
        xbmc_comando,
        vol.Schema({**SCHEMA_BASE, vol.Required("comando"): cv.string, vol.Optional("parametro"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    reg(DOMAIN, "backup_saves", backup_saves, vol.Schema(SCHEMA_BASE), supports_response=SupportsResponse.OPTIONAL)
    reg(DOMAIN, "atualizar_biblioteca", atualizar_biblioteca, vol.Schema(SCHEMA_BASE))
