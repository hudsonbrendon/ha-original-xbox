"""Generate strings.json, translations/{en,pt-BR}.json, services.yaml and icons.json.

Run from the repo root: ``python tools/gen_strings.py``.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "original_xbox"
DOMAIN = "original_xbox"
DRIVES = "cefgxyz"

# key: (English, Brazilian Portuguese)
ENT = {
    "binary_sensor": {
        "ftp": ("Dashboard", "Dashboard"),
        "network": ("Network", "Rede"),
        "frozen": ("Frozen", "Travado"),
    },
    "button": {
        "restart": ("Restart", "Reiniciar"),
        "shut_down": ("Shut down", "Desligar"),
        "open_tray": ("Open tray", "Abrir bandeja"),
        "close_tray": ("Close tray", "Fechar bandeja"),
        "restart_network": ("Restart network", "Reiniciar rede"),
        "restart_ftp": ("Restart FTP", "Reiniciar FTP"),
        "reload_dashboard": ("Reload dashboard", "Recarregar dashboard"),
        "microsoft_dashboard": ("Microsoft dashboard", "Dashboard Microsoft"),
        "backup_saves": ("Back up saves", "Backup dos saves"),
        "refresh_library": ("Refresh library", "Atualizar biblioteca"),
    },
    "image": {"cover": ("Cover", "Capa")},
    "camera": {"screen": ("Screen", "Tela")},
    "remote": {"controller": ("Controller", "Controle")},
    "number": {
        "screensaver_wait": ("Screen saver delay", "Proteção de tela"),
        "auto_turn_off": ("Auto power off", "Desligamento automático"),
    },
    "select": {
        "launch_game": ("Launch game", "Abrir jogo"),
        "launch_app": ("Launch app", "Abrir aplicativo"),
    },
    "sensor": {
        "activity": ("Activity", "Atividade"),
        "current_game": ("Current game", "Jogo atual"),
        "last_game": ("Last game", "Último jogo"),
        "last_session": ("Last session", "Última sessão"),
        "games": ("Games", "Jogos"),
        "apps": ("Apps", "Aplicativos"),
        "saves": ("Saves", "Saves"),
        "library_updated": ("Library updated", "Biblioteca atualizada"),
        "dashboard": ("Dashboard", "Dashboard"),
        "gpu_temperature": ("GPU temperature", "Temperatura da GPU"),
        "cpu_temperature": ("CPU temperature", "Temperatura da CPU"),
        "hdd_temperature": ("Hard drive temperature", "Temperatura do HD"),
        "fan_speed": ("Fan speed", "Ventoinha"),
        "free_memory": ("Free memory", "Memória livre"),
        "xbmc_window": ("XBMC window", "Tela do XBMC"),
        "xbmc_version": ("XBMC version", "Versão do XBMC"),
        **{f"free_{d}": (f"Free {d.upper()}", f"Livre {d.upper()}") for d in DRIVES},
        **{f"usage_{d}": (f"Usage {d.upper()}", f"Uso {d.upper()}") for d in DRIVES},
    },
    "switch": {
        "sntp": ("Sync clock", "Sincronizar relógio"),
        "autolaunch_games": ("Auto-launch games", "Abrir jogo ao inserir disco"),
        "autolaunch_dvd": ("Auto-launch DVD", "Abrir DVD ao inserir"),
        "autolaunch_audiocd": ("Auto-launch audio CD", "Abrir CD de áudio ao inserir"),
        "autolaunch_data": ("Auto-launch data disc", "Abrir disco de dados ao inserir"),
        "newsfeed": ("News feed", "Notícias"),
        "widescreen": ("Widescreen", "Widescreen"),
        "use_1080i": ("1080i", "1080i"),
        "fahrenheit": ("Fahrenheit", "Fahrenheit"),
    },
}
ACTIVITY = {
    "dashboard": ("Dashboard", "Dashboard"),
    "xbmc": ("XBMC", "XBMC"),
    "avalaunch": ("Avalaunch", "Avalaunch"),
    "evox": ("EvolutionX", "EvolutionX"),
    "other_app": ("Other app", "Outro aplicativo"),
    "game": ("In game", "Em jogo"),
    "frozen": ("Frozen", "Travado"),
    "off": ("Off", "Desligado"),
}
# field: (name en, name pt, description en, description pt)
F_ENTRY = {
    "config_entry_id": (
        "Xbox",
        "Xbox",
        "Xbox config entry (optional when only one console is configured).",
        "Entrada do Xbox (opcional se só houver um).",
    )
}
# service: ((name en, name pt), (description en, description pt), fields)
SVC = {
    "launch": (
        ("Launch XBE", "Abrir XBE"),
        (
            r"Launch a game or app by library name or .xbe path (e.g. F:\Games\Halo 2\default.xbe).",
            r"Abre um jogo/app pelo nome da biblioteca ou caminho (ex.: F:\Games\Halo 2\default.xbe).",
        ),
        {"path": ("Path or name", "Caminho ou nome", "Game name or .xbe path.", "Nome do jogo ou caminho do .xbe.")},
    ),
    "site_command": (
        ("SITE command", "Comando SITE"),
        (
            r"Send a raw FTP SITE command to the dashboard (DRIVESTAT, MD5 C:\file, TRAYOPEN...) and return the reply.",
            r"Envia um comando SITE cru ao dashboard (DRIVESTAT, MD5 C:\arquivo, TRAYOPEN...) e devolve a resposta.",
        ),
        {"command": ("Command", "Comando", "E.g. DRIVESTAT", "Ex.: DRIVESTAT")},
    ),
    "upload_file": (
        ("Upload file", "Enviar arquivo"),
        (
            "Upload a file from Home Assistant to the Xbox (ROMs, skins, configs).",
            "Envia um arquivo do HA para o Xbox (ROMs, skins, configs).",
        ),
        {
            "source": (
                "Source",
                "Origem",
                "Path on Home Assistant (must be in allowlist_external_dirs).",
                "Caminho no HA (em allowlist_external_dirs).",
            ),
            "destination": (
                "Destination",
                "Destino",
                "Path on the Xbox; end it with \\ to keep the file name.",
                "Caminho no Xbox; termine com \\ para manter o nome.",
            ),
        },
    ),
    "upload_folder": (
        ("Upload folder (add game)", "Enviar pasta (adicionar jogo)"),
        (
            r"Copy a folder from Home Assistant to the Xbox (default: F:\Games\ plus the folder name) and refresh the library.",
            r"Copia uma pasta do HA para o Xbox, por padrão F:\Games\ + nome da pasta, e atualiza a biblioteca.",
        ),
        {
            "source": (
                "Source folder",
                "Pasta de origem",
                "Folder on Home Assistant containing default.xbe (e.g. /media/games/My Game).",
                "Pasta no HA com o default.xbe (ex.: /media/jogos/Meu Jogo).",
            ),
            "destination": (
                "Destination",
                "Destino",
                r"Optional. Default: F:\Games\ plus the folder name.",
                r"Opcional. Padrão: F:\Games\ + nome da pasta.",
            ),
        },
    ),
    "download_file": (
        ("Download file", "Baixar arquivo"),
        ("Copy a file from the Xbox to Home Assistant.", "Copia um arquivo do Xbox para o HA."),
        {
            "source": ("Source", "Origem", r"Path on the Xbox (e.g. C:\Config.xml).", r"Caminho no Xbox (ex.: C:\Config.xml)."),
            "destination": (
                "Destination",
                "Destino",
                "Path on Home Assistant (must be in allowlist_external_dirs).",
                "Caminho no HA (em allowlist_external_dirs).",
            ),
        },
    ),
    "list_folder": (
        ("List folder", "Listar pasta"),
        ("List a folder on the Xbox.", "Lista uma pasta do Xbox."),
        {"path": ("Folder", "Pasta", r"E.g. F:\Games", r"Ex.: F:\Games")},
    ),
    "xbmc_command": (
        ("XBMC command", "Comando do XBMC"),
        (
            "Run an XBMC command (HTTP API, e.g. ExecBuiltIn with XBMC.ActivateWindow(MyMusic)).",
            "Chama a HTTP API do XBMC (ex.: ExecBuiltIn com XBMC.ActivateWindow(MyMusic)).",
        ),
        {
            "command": ("Command", "Comando", "E.g. GetCurrentlyPlaying", "Ex.: GetCurrentlyPlaying"),
            "parameter": ("Parameter", "Parâmetro", "Optional.", "Opcional."),
        },
    ),
    "backup_saves": (
        ("Back up saves", "Backup dos saves"),
        (
            rf"Zip E:\UDATA into /config/backups/{DOMAIN}/.",
            rf"Baixa E:\UDATA para /config/backups/{DOMAIN}/.",
        ),
        {},
    ),
    "refresh_library": (
        ("Refresh library", "Atualizar biblioteca"),
        ("Rescan games, apps and saves.", "Varre de novo jogos, apps e saves."),
        {},
    ),
}
OPTIONAL_FIELDS = {("xbmc_command", "parameter"), ("upload_folder", "destination")}
CFG = {
    "en": {
        "config": {
            "step": {
                "user": {
                    "title": "Original Xbox",
                    "description": "Leave the Xbox on the dashboard (UnleashX) with FTP enabled.",
                    "data": {"host": "IP address", "username": "FTP user", "password": "FTP password"},
                }
            },
            "error": {
                "cannot_connect": "FTP did not answer. Is the Xbox on and on the dashboard?",
                "invalid_auth": "FTP user or password rejected.",
            },
            "abort": {
                "already_configured": "This Xbox is already configured.",
                "not_xbox": "Not an original Xbox with a supported dashboard.",
            },
            "flow_title": "Xbox ({host})",
        },
        "options": {
            "step": {
                "init": {
                    "title": "Options",
                    "data": {"dashboard": "Dashboard path"},
                    "data_description": {
                        "dashboard": r"XBE reloaded after a settings change (default C:\evoxdash.xbe)."
                    },
                }
            }
        },
    },
    "pt": {
        "config": {
            "step": {
                "user": {
                    "title": "Xbox original",
                    "description": "Deixe o Xbox no dashboard (UnleashX) com o FTP ligado.",
                    "data": {"host": "Endereço IP", "username": "Usuário do FTP", "password": "Senha do FTP"},
                }
            },
            "error": {
                "cannot_connect": "O FTP não respondeu. O Xbox está ligado e no dashboard?",
                "invalid_auth": "Usuário ou senha do FTP recusados.",
            },
            "abort": {
                "already_configured": "Este Xbox já está configurado.",
                "not_xbox": "Não é um Xbox original com dashboard compatível.",
            },
            "flow_title": "Xbox ({host})",
        },
        "options": {
            "step": {
                "init": {
                    "title": "Opções",
                    "data": {"dashboard": "Caminho do dashboard"},
                    "data_description": {
                        "dashboard": r"XBE recarregado depois de mudar configurações (padrão C:\evoxdash.xbe)."
                    },
                }
            }
        },
    },
}
ICONS = {
    "button": {
        "shut_down": "mdi:power",
        "open_tray": "mdi:eject",
        "close_tray": "mdi:eject-outline",
        "restart_network": "mdi:lan-pending",
        "restart_ftp": "mdi:folder-network",
        "reload_dashboard": "mdi:view-dashboard",
        "microsoft_dashboard": "mdi:microsoft-xbox",
        "backup_saves": "mdi:content-save-all",
        "refresh_library": "mdi:bookshelf",
    },
    "image": {"cover": "mdi:image-album"},
    "camera": {"screen": "mdi:television-play"},
    "remote": {"controller": "mdi:controller-classic"},
    "number": {"screensaver_wait": "mdi:monitor-shimmer", "auto_turn_off": "mdi:timer-power"},
    "select": {"launch_game": "mdi:gamepad-variant", "launch_app": "mdi:application"},
    "sensor": {
        "activity": "mdi:microsoft-xbox",
        "current_game": "mdi:gamepad-variant",
        "last_game": "mdi:history",
        "games": "mdi:disc",
        "apps": "mdi:apps",
        "saves": "mdi:content-save",
        "dashboard": "mdi:view-dashboard",
        "library_updated": "mdi:bookshelf",
        "fan_speed": "mdi:fan",
        "free_memory": "mdi:memory",
        "xbmc_window": "mdi:kodi",
        "xbmc_version": "mdi:kodi",
        **{f"free_{d}": "mdi:harddisk" for d in DRIVES},
    },
    "switch": {
        "sntp": "mdi:clock-check",
        "autolaunch_games": "mdi:disc-player",
        "autolaunch_dvd": "mdi:movie-open",
        "autolaunch_audiocd": "mdi:album",
        "autolaunch_data": "mdi:disc",
        "newsfeed": "mdi:newspaper",
        "widescreen": "mdi:monitor",
        "use_1080i": "mdi:television",
        "fahrenheit": "mdi:thermometer",
    },
}
SVC_ICONS = {
    "launch": "mdi:play",
    "site_command": "mdi:console",
    "upload_file": "mdi:upload",
    "upload_folder": "mdi:folder-upload",
    "download_file": "mdi:download",
    "list_folder": "mdi:folder-open",
    "xbmc_command": "mdi:kodi",
    "backup_saves": "mdi:content-save-all",
    "refresh_library": "mdi:bookshelf",
}


def build(i: int, lang: str) -> dict:
    """Build one translation file; i=0 English, i=1 Portuguese."""
    out = json.loads(json.dumps(CFG[lang]))
    ent = {plat: {k: {"name": v[i]} for k, v in keys.items()} for plat, keys in ENT.items()}
    ent["sensor"]["activity"]["state"] = {k: v[i] for k, v in ACTIVITY.items()}
    out["entity"] = ent
    out["services"] = {}
    for svc, (name, desc, fields) in SVC.items():
        f = {k: {"name": v[i], "description": v[2 + i]} for k, v in {**fields, **F_ENTRY}.items()}
        out["services"][svc] = {"name": name[i], "description": desc[i], "fields": f}
    return out


def dump(path: pathlib.Path, data: dict) -> None:
    """Write pretty JSON."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


en, pt = build(0, "en"), build(1, "pt")
dump(ROOT / "strings.json", en)
dump(ROOT / "translations" / "en.json", en)
dump(ROOT / "translations" / "pt-BR.json", pt)
entity_icons = {plat: {k: {"default": v} for k, v in keys.items()} for plat, keys in ICONS.items()}
dump(ROOT / "icons.json", {"entity": entity_icons, "services": {k: {"service": v} for k, v in SVC_ICONS.items()}})
lines = []
for svc, (_, _, fields) in SVC.items():
    lines += [f"{svc}:", "  fields:"]
    for k in fields:
        req = "false" if (svc, k) in OPTIONAL_FIELDS else "true"
        lines += [f"    {k}:", f"      required: {req}", "      selector:", "        text:"]
    lines += [
        "    config_entry_id:",
        "      required: false",
        "      selector:",
        "        config_entry:",
        f"          integration: {DOMAIN}",
    ]
(ROOT / "services.yaml").write_text("\n".join(lines) + "\n")
print("ok")
