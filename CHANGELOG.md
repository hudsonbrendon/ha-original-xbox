# Changelog

## 0.2.0

Renamed to **Original Xbox** (`original_xbox`, repository `ha-original-xbox`) and moved to English.
**Breaking:** existing `xbox_classico` installs must be removed and set up again (or have their
registry migrated).

- Domain `xbox_classico` → `original_xbox`; integration name "Original Xbox".
- Actions renamed: `launch` (`path`), `site_command` (`command`), `xbmc_command` (`command`,
  `parameter`), `upload_file` / `upload_folder` / `download_file` (`source`, `destination`),
  `list_folder` (`path`), `backup_saves`, `refresh_library`; response keys in English.
- Entity translation keys and unique IDs in English; activity states `other_app`, `game`,
  `frozen`, `off`; library categories `games` / `apps` (stored libraries are mapped on load).
- Remote commands in English (`up`, `down`, `left`, `right`, `black`, `white`).
- Code, comments and messages in English; Brazilian Portuguese translation kept.
- Repository tooling aligned with the other integrations: hassfest, HACS validation, ruff + pytest
  on Python 3.14, release on manifest version change, `quality_scale.yaml`, HACS floor 2025.8.0.

## 0.1.7

Last release as `xbox_classico` (Portuguese).
