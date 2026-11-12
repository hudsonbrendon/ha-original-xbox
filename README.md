<p align="center">
  <img src="assets/original-xbox-logo.png" alt="Original Xbox" width="420">
</p>

# Original Xbox for Home Assistant

[![Tests](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/tests.yml/badge.svg)](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/tests.yml)
[![Hassfest](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/hassfest.yml/badge.svg)](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/hassfest.yml)
[![Validate](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/validate.yml/badge.svg)](https://github.com/hudsonbrendon/ha-original-xbox/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/hudsonbrendon/ha-original-xbox)](https://github.com/hudsonbrendon/ha-original-xbox/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Monitor and control a **softmodded or modchipped original Xbox (2001)** from Home Assistant —
what is running, the game library with cover art, disk space, temperatures, power, the
disc tray, dashboard settings, file transfers and XBMC media playback.

> 100% local, nothing to install on the console. Everything goes through the FTP server of the
> dashboard you already run (UnleashX, XBMC/XBMC4Gamers, Avalaunch, EvolutionX), the hidden FTP
> `SITE` commands of UnleashX 0.37 (mapped by reverse engineering) and, when available, the XBMC
> HTTP API. Not affiliated with Microsoft.

## Features

- **Now playing** — a media player that is `off`, `idle` on the dashboard or `playing` a game,
  with the game title and cover art. `select_source` / `play_media` launch any game or app, and the
  media browser lists the whole library with covers. In XBMC: play/pause/stop/next/previous,
  volume, mute and seek.
- **Game library** — scans `Games`, `HDDLoader` and `Apps` on E:/F:/G: (one extra level for folders
  like `Emulators`), reads each XBE header (title, title ID) and its cover (`TitleImage.xbx` or the
  `$$XTIMAGE` section, DXT1 → PNG).
- **Activity** — dashboard / XBMC / Avalaunch / EvolutionX / other app / in game / frozen / off,
  plus current game, last game and last session length.
- **Disks** — free space (GB) and usage (%) of C, E, F, G, X, Y and Z through the hidden
  `SITE DRIVESTAT` command.
- **Power & tray** — restart, shut down, open/close tray, restart network, restart FTP, reload the
  dashboard, boot the Microsoft dashboard.
- **Dashboard settings** — switches and numbers that edit UnleashX `C:\Config.xml` in place
  (clock sync, auto-launch on disc insert, news feed, widescreen, 1080i, Fahrenheit, screen saver,
  auto power off), with a backup on the first write.
- **XBMC telemetry** — GPU/CPU/hard drive temperature, fan speed, free memory, current XBMC window
  and version; screenshot camera and controller remote on XBMC builds with the web server.
- **Frozen detection** — a problem binary sensor when an app hangs (ping answers, FTP stays mute).
- **Saves backup** — zips `E:\UDATA` into `/config/backups/original_xbox/`.
- **File transfers** — upload a file or a whole folder (add a game), download a file, list a folder.
- **Discovery** — consoles are found by DHCP (Microsoft `00:0D:3A` MAC prefix).
- **Diagnostics** — downloadable diagnostics with the FTP password redacted.

## Requirements

- An original Xbox that boots a homebrew dashboard with **FTP enabled** (softmod or modchip).
  Tested on a v1.6 with UnleashX 0.37.1218A, XBMC 2.0 and XBMC4Gamers 3.6.
- FTP credentials (UnleashX default: `xbox` / `xbox`, lowercase).
- A fixed IP for the Xbox (DHCP reservation on the router).
- Optional, for XBMC telemetry, screenshots and the remote on XBMC builds that have it:
  `<webserver>true</webserver>` in `UserData\guisettings.xml`. XBMC4Gamers has no web server; see
  [XBMC4Gamers](#xbmc4gamers-no-web-server).

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/hudsonbrendon/ha-original-xbox`
   as an **Integration**.
2. Install **Original Xbox** and restart Home Assistant.

### Manual

Copy `custom_components/original_xbox` into your `config/custom_components/` folder and restart
Home Assistant.

## Setup

Turn the Xbox on and leave it on the dashboard. It usually shows up under **Settings → Devices &
services → Discovered**; otherwise **Add integration → Original Xbox** and enter:

| Field | Default |
|---|---|
| IP address | — |
| FTP user | `xbox` |
| FTP password | `xbox` |

The flow connects to the FTP server before creating the entry. **Options** let you change the
dashboard XBE that is reloaded after a settings change (default `C:\evoxdash.xbe`).

## Entities

### Media player
State (`off` / `idle` / `playing`), current game with cover, source list = library, media browser
with covers, turn off. In XBMC also playback controls, volume, mute and seek.

### Binary sensors
| Entity | Meaning |
|---|---|
| Dashboard | the dashboard FTP server answers |
| Network | the console answers ping |
| Frozen | an app hung: ping answers but FTP stays mute for 5 min after XBMC |

### Sensors
Activity, current game, last game, last session (min), games, apps, saves, library updated,
dashboard version, free/usage per drive (C, E, F, G, X, Y, Z). In XBMC: GPU/CPU/hard drive
temperature, fan speed, free memory, XBMC window, XBMC version.

### Buttons
Restart (`SITE POWERCYCLE` — `REBOOT` does not work on UnleashX 0.37), shut down, open tray,
close tray, restart network, restart FTP, reload dashboard, Microsoft dashboard, back up saves,
refresh library.

### Selects
Launch game, launch app.

### Switches and numbers (`C:\Config.xml`)
Sync clock (SNTP), auto-launch games / DVD / audio CD / data discs, news feed, widescreen, 1080i,
Fahrenheit; screen saver delay and auto power off.

### Image, camera and remote
Cover of the current (or last) game; XBMC screenshot camera; remote with `up`, `down`, `left`,
`right`, `a`/`ok`, `b`, `x`, `y`, `black`, `white`, `lt`, `rt`, `l3`, `r3`, `start`, `back`.

## Actions

| Action | Fields | Returns |
|---|---|---|
| `original_xbox.launch` | `path` — library name or `.xbe` path | — |
| `original_xbox.site_command` | `command` — raw FTP `SITE` command | `reply` |
| `original_xbox.xbmc_command` | `command`, `parameter` (optional) | `reply` |
| `original_xbox.upload_file` | `source` (HA path), `destination` (Xbox path; end with `\` to keep the name) | — |
| `original_xbox.upload_folder` | `source` (HA folder), `destination` (default `F:\Games\<folder>`) | `destination`, `files`, `bytes`, `skipped` |
| `original_xbox.download_file` | `source` (Xbox path), `destination` (HA path) | `file`, `bytes` |
| `original_xbox.list_folder` | `path` | `items` (`name`, `is_dir`, `size`) |
| `original_xbox.backup_saves` | — | `file` |
| `original_xbox.refresh_library` | — | — |

Every action also takes an optional `config_entry_id` when more than one console is configured.
Paths on Home Assistant must be in
[`allowlist_external_dirs`](https://www.home-assistant.io/integrations/homeassistant/#allowlist_external_dirs).
`upload_folder` skips names FATX rejects (longer than 42 characters or with invalid characters) and
returns them in `skipped`.

### Examples

```yaml
# Launch a game by its library name
action: original_xbox.launch
data:
  path: Halo 2

# Add a game copied to /media
action: original_xbox.upload_folder
data:
  source: /media/xbox/Crash Twinsanity

# Free space on every partition
action: original_xbox.site_command
data:
  command: DRIVESTAT
```

Turn the lights down when a game starts:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.original_xbox_activity
    to: game
actions:
  - action: scene.turn_on
    target:
      entity_id: scene.gaming
```

## How it works

- **State** — every 15 s Home Assistant connects to FTP; the banner tells which app is open
  (`UnleashX`, `FileZilla (XBMC)`, ...). Without FTP, a ping tells *in game* from *off* when the game
  keeps the network up; games launched from Home Assistant stay marked until the dashboard returns.
- **Launching** — `SITE EXEC <xbe>` on UnleashX, `RunXBE` on XBMC. After any command that closes the
  app, Home Assistant stays quiet for 25 s, because XBMC 2.0 freezes if it is queried while closing.
- **Disks** — the hidden `SITE DRIVESTAT` returns used/free/total for every partition.
- **Config.xml** — edited in place (only the value changes), backed up to `C:\Config.xml.ha-backup`
  on the first write; the dashboard is reloaded to apply it.

### UnleashX 0.37 FTP `SITE` commands (reverse engineered)

`REBOOT`/`RESTART` (call `XLaunchNewImage(NULL)` and fail silently in this build), `SHUTDOWN`,
`POWERCYCLE` (really restarts; replies 502 after acting), `FTPRESET`, `FTPSTOP`, `NETRESET`,
`TRAYOPEN`/`EJECT`, `TRAYCLOSE`, `DRIVESTAT`, `EXEC <xbe>`, `LAUNCH <xbe>`, `MD5 <file>`,
`XBERENAME`, `FREESPACE <drive>`, `FREEROOTSPACEDISABLE`, `TITLES`, `TITLEIMAGE`, `MAKE_FILE_TREE`.

### XBMC4Gamers (no web server)

XBMC4Gamers ships without the web server, so the integration uses the built-ins of the XBMC FTP
server (`SITE RunXBE`, `PlayerControl`, `SetVolume`, `Mute`, `Reboot`, `ShutDown`) and reads the
telemetry (temperatures, fan, memory, window, now playing) with a small Python 2 script it installs
in `E:\TDATA\ha_original_xbox` and runs through `SITE RunScript`.

## Known limitations

- **No control while a game runs.** Games do not run an FTP server; Home Assistant only knows the
  console is in a game (ping plus the last launch) until you go back to the dashboard.
- **No power on.** The original Xbox has no Wake-on-LAN.
- **Camera and remote need the XBMC HTTP API**, which XBMC4Gamers does not have.
- **XBMC4Gamers memory.** Running the telemetry script repeatedly while music plays crashed the
  console in tests, so while media plays the next read only happens at the expected end of the track
  and media commands update the state optimistically.
- **XBMC 2.0 freezes** if queried while it closes to launch another XBE; the 25 s quiet period
  avoids it, and the Frozen sensor reports it when it still happens (only the power button helps).

## Troubleshooting

- **Cannot connect** — the console must be on the dashboard with FTP enabled; try
  `ftp <ip>` from a computer with the same credentials. UnleashX credentials are case sensitive.
- **Entities unavailable** — most controls need the dashboard (UnleashX) or XBMC open; they are
  unavailable in games by design.
- **Debug logs** — add to `configuration.yaml`:

  ```yaml
  logger:
    logs:
      custom_components.original_xbox: debug
  ```

## Removal

Settings → Devices & services → Original Xbox → ⋮ → **Delete**, then remove the repository from
HACS (or delete `custom_components/original_xbox`) and restart. Optionally delete
`E:\TDATA\ha_original_xbox` on the console and `/config/backups/original_xbox`.

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest
```

`python tools/gen_strings.py` regenerates `strings.json`, the translations, `services.yaml` and
`icons.json`.

## License

[MIT](LICENSE)
