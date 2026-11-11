"""Gera strings.json, translations/{en,pt-BR}.json, services.yaml e icons.json."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "xbox_classico"
DRIVES = "cefgxyz"
# chave: (pt, en)
ENT = {
  "binary_sensor": {"ftp": ("Dashboard", "Dashboard"), "rede": ("Rede", "Network")},
  "button": {
    "reiniciar": ("Reiniciar", "Restart"), "desligar": ("Desligar", "Shut down"),
    "reinicio_completo": ("Reinício completo", "Power cycle"), "abrir_bandeja": ("Abrir bandeja", "Open tray"),
    "fechar_bandeja": ("Fechar bandeja", "Close tray"), "reiniciar_rede": ("Reiniciar rede", "Restart network"),
    "reiniciar_ftp": ("Reiniciar FTP", "Restart FTP"), "recarregar_dashboard": ("Recarregar dashboard", "Reload dashboard"),
    "dashboard_microsoft": ("Dashboard Microsoft", "Microsoft dashboard"), "backup_saves": ("Backup dos saves", "Back up saves"),
    "atualizar_biblioteca": ("Atualizar biblioteca", "Refresh library")},
  "image": {"capa": ("Capa", "Cover")},
  "camera": {"tela": ("Tela", "Screen")},
  "remote": {"controle": ("Controle", "Controller")},
  "number": {"screensaver_wait": ("Proteção de tela", "Screen saver delay"), "auto_turn_off": ("Desligamento automático", "Auto power off")},
  "select": {"abrir_jogo": ("Abrir jogo", "Launch game"), "abrir_aplicativo": ("Abrir aplicativo", "Launch app")},
  "sensor": {
    "atividade": ("Atividade", "Activity"), "jogo_atual": ("Jogo atual", "Current game"),
    "ultimo_jogo": ("Último jogo", "Last game"), "ultima_sessao": ("Última sessão", "Last session"),
    "jogos": ("Jogos", "Games"), "aplicativos": ("Aplicativos", "Apps"), "saves": ("Saves", "Saves"),
    "biblioteca_atualizada": ("Biblioteca atualizada", "Library updated"), "dashboard": ("Dashboard", "Dashboard"),
    "temperatura_gpu": ("Temperatura da GPU", "GPU temperature"), "temperatura_cpu": ("Temperatura da CPU", "CPU temperature"),
    "ventoinha": ("Ventoinha", "Fan speed"), "memoria_livre": ("Memória livre", "Free memory"),
    "tela_xbmc": ("Tela do XBMC", "XBMC window"), "versao_xbmc": ("Versão do XBMC", "XBMC version"),
    **{f"livre_{d}": (f"Livre {d.upper()}", f"Free {d.upper()}") for d in DRIVES},
    **{f"uso_{d}": (f"Uso {d.upper()}", f"Usage {d.upper()}") for d in DRIVES}},
  "switch": {
    "sntp": ("Sincronizar relógio", "Sync clock"), "autolaunch_games": ("Abrir jogo ao inserir disco", "Auto-launch games"),
    "autolaunch_dvd": ("Abrir DVD ao inserir", "Auto-launch DVD"), "autolaunch_audiocd": ("Abrir CD de áudio ao inserir", "Auto-launch audio CD"),
    "autolaunch_data": ("Abrir disco de dados ao inserir", "Auto-launch data disc"), "newsfeed": ("Notícias", "News feed"),
    "widescreen": ("Widescreen", "Widescreen"), "use_1080i": ("1080i", "1080i"), "fahrenheit": ("Fahrenheit", "Fahrenheit")},
}
ACT = {"dashboard": ("Dashboard", "Dashboard"), "xbmc": ("XBMC", "XBMC"), "avalaunch": ("Avalaunch", "Avalaunch"),
       "evox": ("EvolutionX", "EvolutionX"), "outro_app": ("Outro aplicativo", "Other app"), "jogo": ("Em jogo", "In game"),
       "desligado": ("Desligado", "Off")}
F_ENTRY = {"config_entry_id": ("Xbox", "Xbox", "Entrada do Xbox (opcional se só houver um).", "Xbox entry (optional with one console).")}
SVC = {
  "executar": (("Abrir XBE", "Launch XBE"), ("Abre um jogo/app pelo nome da biblioteca ou caminho (ex.: F:\\Games\\Halo 2\\default.xbe).", "Launch a game/app by library name or path."),
               {"caminho": ("Caminho ou nome", "Path or name", "Nome do jogo ou caminho do .xbe.", "Game name or .xbe path.")}),
  "comando_site": (("Comando SITE", "SITE command"), ("Envia um comando SITE cru ao UnleashX (DRIVESTAT, MD5 C:\\arquivo, TRAYOPEN...).", "Send a raw SITE command to UnleashX."),
               {"comando": ("Comando", "Command", "Ex.: DRIVESTAT", "E.g. DRIVESTAT")}),
  "enviar_arquivo": (("Enviar arquivo", "Upload file"), ("Envia um arquivo do HA para o Xbox (ROMs, skins, configs).", "Upload a file from HA to the Xbox."),
               {"origem": ("Origem", "Source", "Caminho no HA (em allowlist_external_dirs).", "Path on HA."),
                "destino": ("Destino", "Destination", "Caminho no Xbox; termine com \\ para manter o nome.", "Path on the Xbox.")}),
  "baixar_arquivo": (("Baixar arquivo", "Download file"), ("Copia um arquivo do Xbox para o HA.", "Copy a file from the Xbox to HA."),
               {"origem": ("Origem", "Source", "Caminho no Xbox (ex.: C:\\Config.xml).", "Path on the Xbox."),
                "destino": ("Destino", "Destination", "Caminho no HA (em allowlist_external_dirs).", "Path on HA.")}),
  "xbmc_comando": (("Comando do XBMC", "XBMC command"), ("Chama a HTTP API do XBMC (ex.: ExecBuiltIn com XBMC.ActivateWindow(MyMusic)).", "Call the XBMC HTTP API."),
               {"comando": ("Comando", "Command", "Ex.: GetCurrentlyPlaying", "E.g. GetCurrentlyPlaying"),
                "parametro": ("Parâmetro", "Parameter", "Opcional.", "Optional.")}),
  "listar": (("Listar pasta", "List folder"), ("Lista uma pasta do Xbox.", "List a folder on the Xbox."),
               {"caminho": ("Pasta", "Folder", "Ex.: F:\\Games", "E.g. F:\\Games")}),
  "backup_saves": (("Backup dos saves", "Back up saves"), ("Baixa E:\\UDATA para /config/backups/xbox_classico/.", "Download E:\\UDATA to /config/backups/xbox_classico/."), {}),
  "atualizar_biblioteca": (("Atualizar biblioteca", "Refresh library"), ("Varre de novo jogos, apps e saves.", "Rescan games, apps and saves."), {}),
}
CFG = {
  "pt": {"config": {"step": {"user": {"title": "Xbox Clássico", "description": "Deixe o Xbox no dashboard (UnleashX) com o FTP ligado.",
          "data": {"host": "Endereço IP", "username": "Usuário do FTP", "password": "Senha do FTP"}}},
          "error": {"cannot_connect": "O FTP não respondeu. O Xbox está ligado e no dashboard?", "invalid_auth": "Usuário ou senha do FTP recusados."},
          "abort": {"already_configured": "Este Xbox já está configurado.", "not_xbox": "Não é um Xbox clássico com dashboard compatível."},
          "flow_title": "Xbox ({host})"},
         "options": {"step": {"init": {"title": "Opções", "data": {"dashboard": "Caminho do dashboard"},
          "data_description": {"dashboard": "XBE recarregado depois de mudar configurações (padrão C:\\evoxdash.xbe)."}}}}},
  "en": {"config": {"step": {"user": {"title": "Classic Xbox", "description": "Leave the Xbox on the dashboard (UnleashX) with FTP enabled.",
          "data": {"host": "IP address", "username": "FTP user", "password": "FTP password"}}},
          "error": {"cannot_connect": "FTP did not answer. Is the Xbox on the dashboard?", "invalid_auth": "FTP user or password rejected."},
          "abort": {"already_configured": "This Xbox is already configured.", "not_xbox": "Not a classic Xbox with a supported dashboard."},
          "flow_title": "Xbox ({host})"},
         "options": {"step": {"init": {"title": "Options", "data": {"dashboard": "Dashboard path"},
          "data_description": {"dashboard": "XBE reloaded after settings change (default C:\\evoxdash.xbe)."}}}}},
}
ICONS = {"button": {"desligar": "mdi:power", "abrir_bandeja": "mdi:eject", "fechar_bandeja": "mdi:eject-outline",
  "reiniciar_rede": "mdi:lan-pending", "reiniciar_ftp": "mdi:folder-network", "recarregar_dashboard": "mdi:view-dashboard",
  "dashboard_microsoft": "mdi:microsoft-xbox", "backup_saves": "mdi:content-save-all", "atualizar_biblioteca": "mdi:bookshelf"},
  "image": {"capa": "mdi:image-album"},
  "camera": {"tela": "mdi:television-play"}, "remote": {"controle": "mdi:controller-classic"},
  "number": {"screensaver_wait": "mdi:monitor-shimmer", "auto_turn_off": "mdi:timer-power"},
  "select": {"abrir_jogo": "mdi:gamepad-variant", "abrir_aplicativo": "mdi:application"},
  "sensor": {"atividade": "mdi:microsoft-xbox", "jogo_atual": "mdi:gamepad-variant", "ultimo_jogo": "mdi:history",
    "jogos": "mdi:disc", "aplicativos": "mdi:apps", "saves": "mdi:content-save", "dashboard": "mdi:view-dashboard",
    "biblioteca_atualizada": "mdi:bookshelf", "ventoinha": "mdi:fan", "memoria_livre": "mdi:memory",
    "tela_xbmc": "mdi:kodi", "versao_xbmc": "mdi:kodi", **{f"livre_{d}": "mdi:harddisk" for d in DRIVES}},
  "switch": {"sntp": "mdi:clock-check", "autolaunch_games": "mdi:disc-player", "autolaunch_dvd": "mdi:movie-open",
    "autolaunch_audiocd": "mdi:album", "autolaunch_data": "mdi:disc", "newsfeed": "mdi:newspaper", "widescreen": "mdi:monitor",
    "use_1080i": "mdi:television", "fahrenheit": "mdi:thermometer"}}
SVC_ICONS = {"executar": "mdi:play", "comando_site": "mdi:console", "enviar_arquivo": "mdi:upload", "baixar_arquivo": "mdi:download",
  "listar": "mdi:folder-open", "xbmc_comando": "mdi:kodi", "backup_saves": "mdi:content-save-all", "atualizar_biblioteca": "mdi:bookshelf"}

def build(i, lang):
    out = json.loads(json.dumps(CFG[lang]))
    ent = {}
    for plat, keys in ENT.items():
        ent[plat] = {k: {"name": v[i]} for k, v in keys.items()}
    ent["sensor"]["atividade"]["state"] = {k: v[i] for k, v in ACT.items()}
    out["entity"] = ent
    out["services"] = {}
    for s, (name, desc, fields) in SVC.items():
        f = {k: {"name": v[i], "description": v[2 + i]} for k, v in {**fields, **F_ENTRY}.items()}
        out["services"][s] = {"name": name[i], "description": desc[i], "fields": f}
    return out

en, pt = build(1, "en"), build(0, "pt")
(ROOT / "strings.json").write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n")
(ROOT / "translations" / "en.json").write_text(json.dumps(en, ensure_ascii=False, indent=2) + "\n")
(ROOT / "translations" / "pt-BR.json").write_text(json.dumps(pt, ensure_ascii=False, indent=2) + "\n")
(ROOT / "icons.json").write_text(json.dumps({"entity": ICONS, "services": {k: {"service": v} for k, v in SVC_ICONS.items()}}, indent=2) + "\n")
lines = []
for s, (_, _, fields) in SVC.items():
    lines.append(f"{s}:")
    lines.append("  fields:")
    for k in fields:
        req = "false" if k == "parametro" else "true"
        lines += [f"    {k}:", f"      required: {req}", "      selector:", "        text:"]
    lines += ["    config_entry_id:", "      required: false", "      selector:", "        config_entry:", "          integration: xbox_classico"]
(ROOT / "services.yaml").write_text("\n".join(lines) + "\n")
print("ok")
