"""Coordinator: estado pelo FTP do dashboard + ping; biblioteca, saves e capas em cache."""

from __future__ import annotations

import asyncio
import os
import socket
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    APP_AVALAUNCH,
    APP_DASHBOARD,
    APP_EVOX,
    APP_XBMC,
    XbmcClient,
    XboxClient,
    XboxError,
    XboxHung,
    FTP_APPS,
    XboxOffline,
    offline_activity,
    parse_duration,
    parse_config,
    set_config,
)
from .const import (
    ACT_AVALAUNCH,
    ACT_DASHBOARD,
    ACT_EVOX,
    ACT_GAME,
    ACT_HUNG,
    ACT_OFF,
    ACT_OTHER,
    ACT_XBMC,
    CONF_DASHBOARD,
    CONFIG_PATH,
    CONFIG_REFRESH_SECONDS,
    DEFAULT_DASHBOARD,
    DEFAULT_ROOTS,
    DOMAIN,
    DRIVES_REFRESH_SECONDS,
    LIBRARY_REFRESH_SECONDS,
    LOGGER,
    QUIET_AFTER_LAUNCH_SECONDS,
    SCAN_INTERVAL_SECONDS,
    SESSION_GIVE_UP_SECONDS,
    XBMC_SYSTEM_SECONDS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

APP_TO_ACTIVITY = {APP_DASHBOARD: ACT_DASHBOARD, APP_XBMC: ACT_XBMC, APP_AVALAUNCH: ACT_AVALAUNCH, APP_EVOX: ACT_EVOX}
APP_NAMES = {ACT_XBMC: "Xbox Media Center", ACT_AVALAUNCH: "Avalaunch", ACT_EVOX: "EvolutionX"}
STORE_VERSION = 1


async def async_ping(host: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", host, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        return await asyncio.wait_for(proc.wait(), 4) == 0
    except (OSError, TimeoutError):
        return False


class XboxCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """data = {online, ping, activity, app, banner, system, drives, config, current, last}."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: XboxClient) -> None:
        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS)
        )
        self.client = client
        self.xbmc = XbmcClient(client.host)
        self.xbmc_status: dict | None = None
        self._xbmc_system: dict = {}
        self._xbmc_system_at = 0.0
        self._script_ok = False
        self._script_next = 0.0  # próxima execução do ha_info.py
        self.console_info: dict = {}  # versão do Xbox, BIOS, kernel (do script no XBMC)
        self._quiet_until = 0.0
        self._silent_since: float | None = None
        self.library: list[dict] = []
        self.saves: list[dict] = []
        self.config_text: str | None = None
        self.config: dict[str, Any] = {}
        self.drives: dict[str, dict[str, float]] = {}
        self.system: str | None = None
        self.current: dict | None = None  # jogo/app lançado pelo HA e ainda rodando
        self.last: dict | None = None  # última sessão encerrada
        self.library_at = 0.0
        self._drives_at = 0.0
        self._config_at = 0.0
        self._scan_task: asyncio.Task | None = None
        self._rescan = False
        self._covers: dict[str, bytes | None] = {}
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._covers_dir = hass.config.path(f".storage/{DOMAIN}_covers")

    @property
    def dashboard_path(self) -> str:
        return self.config_entry.options.get(CONF_DASHBOARD, DEFAULT_DASHBOARD)

    # ------------------------------------------------------------ persistência

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.library = data.get("library", [])
        self.saves = data.get("saves", [])
        self.last = data.get("last")
        self.current = data.get("current")
        self.system = data.get("system")
        self.library_at = data.get("library_at", 0.0)
        self.console_info = data.get("console_info", {})

    def _save(self) -> None:
        self._store.async_delay_save(
            lambda: {
                "library": self.library,
                "saves": self.saves,
                "last": self.last,
                "current": self.current,
                "system": self.system,
                "library_at": self.library_at,
                "console_info": self.console_info,
            },
            5,
        )

    # ------------------------------------------------------------ polling

    async def _async_update_data(self) -> dict[str, Any]:
        if time.time() < self._quiet_until and self.data:
            # logo depois de lançar/reiniciar: não tocar no console enquanto o app fecha
            return {**self.data, "at": dt_util.utcnow()}
        hung = False
        try:
            probe = await self.hass.async_add_executor_job(self.client.probe)
        except XboxHung:
            probe, hung = None, True
        except XboxOffline:
            probe = None
        except XboxError as err:
            LOGGER.debug("FTP respondeu mas falhou: %s", err)
            probe = None

        now = time.time()
        if probe is None:
            ping = await async_ping(self.client.host)
            if self.current and now - self.current["started"] > SESSION_GIVE_UP_SECONDS:
                self._end_session(now)
            prev = (self.data or {}).get("activity")
            if self.current and self.current.get("activity") in FTP_APPS:
                prev = self.current["activity"]  # sessão aberta num app com FTP (ex.: XBMC)
            activity, self._silent_since = offline_activity(
                prev, hung, ping, self.current is not None, self._silent_since, now
            )
            return self._data(False, ping, activity, None)

        self._silent_since = None
        activity = APP_TO_ACTIVITY.get(probe["app"], ACT_OTHER)
        if activity == ACT_DASHBOARD:
            self.system = probe["system"] or self.system
            if self.current:
                self._end_session(now)
            await self._refresh_dashboard_extras(now)
        elif self.current and self.current.get("activity") == ACT_GAME and self.current.get("by_ha"):
            # o app que o HA abriu subiu o FTP dele (ex.: XBMC): mesma sessão
            self.current["activity"] = activity
            self._save()
        elif self.current is None or self.current.get("activity") != activity:
            # app com FTP próprio aberto pelo controle (ou trocado depois do lançamento)
            if self.current:
                self._end_session(now)
            self.current = {
                "name": APP_NAMES.get(activity, "Aplicativo"),
                "path": None,
                "title_id": None,
                "started": now,
                "activity": activity,
                "by_ha": False,
            }
            self._save()
        self.xbmc_status = None
        if activity == ACT_XBMC:
            try:
                with_system = now - self._xbmc_system_at > XBMC_SYSTEM_SECONDS
                status = await self.hass.async_add_executor_job(self.xbmc.status, with_system)
                if with_system:
                    self._xbmc_system = {k: status.get(k) for k in ("gpu_temp", "cpu_temp", "fan", "free_memory", "build")}
                    self._xbmc_system_at = now
                self._xbmc_system = {**self._xbmc_system, "window": status.get("window")}
                self.xbmc_status = {**status, **self._xbmc_system}
            except XboxError as err:
                LOGGER.debug("HTTP do XBMC indisponível (webserver ligado?): %s", err)
                if now >= self._script_next:
                    await self._xbmc_script_telemetry(now)
        return self._data(True, True, activity, probe)

    async def _xbmc_script_telemetry(self, now: float) -> None:
        """XBMC sem servidor web (XBMC4Gamers): telemetria pelo ha_info.py via SITE RunScript.

        Rodar o script várias vezes com mídia tocando derrubou o console 3 de 3 vezes
        (XBMC4Gamers 3.6, ~33 MB livres); uma execução isolada foi segura. Então, com mídia
        tocando, a próxima leitura só acontece depois do fim previsto da faixa."""
        self._xbmc_system_at = now
        self._script_next = now + XBMC_SYSTEM_SECONDS
        try:
            info = await self.hass.async_add_executor_job(self.client.run_xbmc_script, not self.console_info)
        except XboxError as err:
            LOGGER.debug("telemetria por script falhou: %s", err)
            return
        self._xbmc_system = {
            k: info.get(k)
            for k in ("gpu_temp", "cpu_temp", "hdd_temp", "fan", "free_memory", "build", "window", "playing")
        }
        playing = info.get("playing")
        if playing:
            left = (parse_duration(playing.get("Duration")) or 0) - (parse_duration(playing.get("Time")) or 0)
            self._script_next = now + max(XBMC_SYSTEM_SECONDS, left + 10)
        console = {k: info[k] for k in ("xbox_version", "bios", "kernel", "produced", "cpu_frequency") if info.get(k)}
        if console and console != self.console_info:
            self.console_info = {**self.console_info, **console}
            self._save()
            self._update_device()

    def _update_device(self) -> None:
        reg = dr.async_get(self.hass)
        device = reg.async_get_device(identifiers={(DOMAIN, self.config_entry.unique_id)})
        if device is None or not self.console_info:
            return
        info = self.console_info
        reg.async_update_device(
            device.id,
            model=f"Xbox {info['xbox_version']}" if info.get("xbox_version") else device.model,
            hw_version=info.get("bios") or device.hw_version,
        )

    def _data(self, online: bool, ping: bool, activity: str, probe: dict | None) -> dict[str, Any]:
        return {
            "online": online,
            "ping": ping,
            "activity": activity,
            "banner": probe["banner"] if probe else None,
            "current": self.current,
            "last": self.last,
            "xbmc": self.xbmc_status if activity == ACT_XBMC else None,
            "telemetria": self._xbmc_system if activity == ACT_XBMC else None,
            "at": dt_util.utcnow(),
        }

    async def _refresh_dashboard_extras(self, now: float) -> None:
        if not self._script_ok:
            try:
                await self.hass.async_add_executor_job(self.client.ensure_script)
                self._script_ok = True
            except XboxError as err:
                LOGGER.debug("não instalou o script de telemetria: %s", err)
        if now - self._drives_at > DRIVES_REFRESH_SECONDS:
            try:
                self.drives = await self.hass.async_add_executor_job(self.client.drivestat)
                self._drives_at = now
            except XboxError as err:
                LOGGER.debug("DRIVESTAT falhou: %s", err)
        if now - self._config_at > CONFIG_REFRESH_SECONDS:
            try:
                raw = await self.hass.async_add_executor_job(self.client.read, CONFIG_PATH)
                self.config_text = raw.decode("utf-8", "replace")
                self.config = parse_config(self.config_text)
                self._config_at = now
            except XboxError as err:
                LOGGER.debug("Config.xml falhou: %s", err)
        if now - self.library_at > LIBRARY_REFRESH_SECONDS and not self.scanning:
            self.async_start_scan()

    # ------------------------------------------------------------ sessões

    def _end_session(self, now: float) -> None:
        cur = self.current
        self.current = None
        if cur:
            self.last = {**cur, "ended": now, "minutes": round((now - cur["started"]) / 60, 1)}
        self._save()

    def find_item(self, name_or_path: str) -> dict | None:
        key = name_or_path.casefold()
        return next(
            (i for i in self.library if i["path"].casefold() == key or i["name"].casefold() == key),
            None,
        )

    def quiet(self) -> None:
        self._quiet_until = time.time() + QUIET_AFTER_LAUNCH_SECONDS
        self._xbmc_system_at = 0.0

    async def async_launch(self, path: str) -> None:
        """SITE EXEC: o dashboard fecha e o XBE abre (o FTP cai até voltar ao dashboard)."""
        activity = (self.data or {}).get("activity")
        item = self.find_item(path) or {"name": path.rsplit("\\", 1)[-1], "path": path, "title_id": None}
        if activity == ACT_XBMC and self.xbmc_status is not None:
            reply = await self.hass.async_add_executor_job(self.xbmc.builtin, f"XBMC.RunXBE({item['path']})")
        elif activity == ACT_XBMC:
            # sem servidor web (ex.: XBMC4Gamers): built-in pelo SITE do FTP do XBMC
            reply = await self.hass.async_add_executor_job(self.client.site_fire, f"RunXBE({item['path']})")
        elif activity == ACT_DASHBOARD:
            reply = await self.hass.async_add_executor_job(self.client.execute, item["path"])
        else:
            raise XboxError("o Xbox precisa estar no dashboard (ou no XBMC com o servidor web) para abrir jogos")
        if "fail" in reply.lower() or reply.startswith("5"):
            raise XboxError(f"Xbox recusou: {reply}")
        self.quiet()
        now = time.time()
        is_dash = item["path"].casefold() == self.dashboard_path.casefold()
        if not is_dash:
            self.current = {
                "name": item["name"],
                "path": item["path"],
                "title_id": item.get("title_id"),
                "started": now,
                "activity": ACT_GAME,
                "by_ha": True,
            }
            self._save()
        self.async_set_updated_data(self._data(False, True, ACT_GAME if not is_dash else ACT_DASHBOARD, None))

    async def async_power(self, command: str) -> None:
        """REBOOT/SHUTDOWN/POWERCYCLE pelo UnleashX ou pelo XBMC, conforme quem está aberto."""
        activity = (self.data or {}).get("activity")
        if activity == ACT_XBMC and self.xbmc_status is not None:
            builtin = {"POWERCYCLE": "XBMC.Reboot", "REBOOT": "XBMC.Reboot", "SHUTDOWN": "XBMC.Shutdown"}[command]
            await self.hass.async_add_executor_job(self.xbmc.builtin, builtin)
            self.quiet()
        elif activity == ACT_XBMC:
            site = {"POWERCYCLE": "Reboot", "REBOOT": "Reboot", "SHUTDOWN": "ShutDown"}[command]
            await self.hass.async_add_executor_job(self.client.site_fire, site)
            self.quiet()
        elif activity == ACT_DASHBOARD:
            await self.async_site(command, fire=True)
            self.quiet()
        else:
            raise XboxError("comando indisponível: o Xbox não está no dashboard nem no XBMC")

    # comando -> (HTTP API, parâmetro?) | built-in pelo SITE do FTP do XBMC
    _MEDIA = {
        "pause": ("Pause", "PlayerControl(Play)"),
        "stop": ("Stop", "PlayerControl(Stop)"),
        "next": ("PlayNext", "PlayerControl(Next)"),
        "previous": ("PlayPrev", "PlayerControl(Previous)"),
        "mute": ("Mute", "Mute"),
        "volume": ("SetVolume", "SetVolume({})"),
        "seek": ("SeekPercentage", None),
    }

    async def async_media(self, action: str, value: int | None = None) -> None:
        """Controle de mídia no XBMC: HTTP API se houver, senão SITE do FTP (XBMC4Gamers)."""
        if (self.data or {}).get("activity") != ACT_XBMC:
            raise XboxError("o XBMC não está aberto")
        http, site = self._MEDIA[action]
        if self.xbmc_status is not None:
            await self.async_xbmc(http, None if value is None else str(value))
            return
        if site is None:
            raise XboxError("sem o servidor web do XBMC não dá para pular para uma posição")
        await self.async_site(site.format(value))
        # sem reler pelo script (arriscado com mídia tocando): atualiza o estado na hora
        playing = dict(self._xbmc_system.get("playing") or {})
        if action == "stop":
            playing = {}
            self._script_next = time.time() + XBMC_SYSTEM_SECONDS
        elif action == "pause" and playing:
            playing["PlayStatus"] = "Playing" if playing.get("PlayStatus") == "Paused" else "Paused"
        elif action in ("next", "previous"):
            self._script_next = time.time() + 5  # uma leitura para pegar a faixa nova
        self._xbmc_system = {**self._xbmc_system, "playing": playing or None}
        if self.data:
            self.async_set_updated_data({**self.data, "telemetria": self._xbmc_system})

    async def async_xbmc(self, command: str, parameter: str | None = None) -> str:
        if (self.data or {}).get("activity") != ACT_XBMC:
            raise XboxError("o XBMC não está aberto")
        return " ".join(await self.hass.async_add_executor_job(self.xbmc.lines, command, parameter))

    async def async_site(self, command: str, fire: bool = False) -> str:
        func = self.client.site_fire if fire else self.client.site
        return await self.hass.async_add_executor_job(func, command)

    # ------------------------------------------------------------ biblioteca

    @property
    def scanning(self) -> bool:
        return self._scan_task is not None and not self._scan_task.done()

    def async_start_scan(self) -> None:
        if self.scanning:
            self._rescan = True  # pedido durante uma varredura: roda de novo ao terminar
            return
        self._scan_task = self.config_entry.async_create_background_task(
            self.hass, self._async_scan(), f"{DOMAIN}_scan"
        )

    async def _async_scan(self) -> None:
        known = {i["path"]: i for i in self.library}
        try:
            library = await self.hass.async_add_executor_job(self.client.scan_library, DEFAULT_ROOTS, known)
            saves = await self.hass.async_add_executor_job(self.client.saves)
        except XboxError as err:
            LOGGER.info("varredura da biblioteca interrompida: %s", err)
            return
        seen: set[str] = set()
        self.library = [i for i in library if not (i["path"].casefold() in seen or seen.add(i["path"].casefold()))]
        self.saves = saves
        self.library_at = time.time()
        self._save()
        for item in self.library:
            if (self.data or {}).get("activity") != ACT_DASHBOARD:
                break
            if item.get("title_id") and item["title_id"] not in self._covers:
                await self.async_cover(item["title_id"], item["path"])
        LOGGER.info("biblioteca do Xbox: %d itens, %d pastas de save", len(self.library), len(saves))
        self.async_update_listeners()
        if self._rescan:
            self._rescan = False
            self.hass.async_create_task(self._async_scan(), f"{DOMAIN}_rescan")

    # ------------------------------------------------------------ capas

    async def async_cover(self, title_id: str | None, xbe_path: str | None = None) -> bytes | None:
        if not title_id:
            return None
        if title_id in self._covers and (self._covers[title_id] or not (self.data or {}).get("online")):
            return self._covers[title_id]
        file = os.path.join(self._covers_dir, f"{title_id}.png")
        png = await self.hass.async_add_executor_job(_read_file, file)
        if png is None and (self.data or {}).get("activity") == ACT_DASHBOARD and time.time() >= self._quiet_until:
            if xbe_path is None:
                xbe_path = next((i["path"] for i in self.library if i.get("title_id") == title_id), None)
            try:
                png = await self.hass.async_add_executor_job(self.client.title_image, title_id, xbe_path)
            except XboxError as err:
                LOGGER.debug("capa %s falhou: %s", title_id, err)
                return None
            if png:
                await self.hass.async_add_executor_job(_write_file, file, png)
        self._covers[title_id] = png
        return png

    # ------------------------------------------------------------ Config.xml

    async def async_set_config(self, key: str, value: Any) -> None:
        if (self.data or {}).get("activity") != ACT_DASHBOARD:
            raise XboxError("o Xbox precisa estar no dashboard para mudar a configuração")
        raw = await self.hass.async_add_executor_job(self.client.read, CONFIG_PATH)
        text = raw.decode("utf-8", "replace")
        if key == "sntp" and value:
            text = set_config(text, "sntp_server", await self.hass.async_add_executor_job(_ntp_ip))
        new = set_config(text, key, value)
        if new == text:
            return
        backup = CONFIG_PATH + ".ha-backup"
        if await self.hass.async_add_executor_job(self.client.md5, backup) is None:
            await self.hass.async_add_executor_job(self.client.write, backup, raw)
        await self.hass.async_add_executor_job(self.client.write, CONFIG_PATH, new.encode("utf-8"))
        self.config_text = new
        self.config = parse_config(new)
        # o UnleashX só relê o Config.xml ao abrir: recarrega o dashboard
        await self.hass.async_add_executor_job(self.client.execute, self.dashboard_path)
        self.quiet()
        self.async_update_listeners()


def _ntp_ip() -> str:
    try:
        return socket.gethostbyname("a.ntp.br")
    except OSError:
        return "200.160.0.8"


def _read_file(path: str) -> bytes | None:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _write_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
