# Xbox Clássico para Home Assistant

Controla um **Xbox original desbloqueado** (softmod ou chip) pelo Home Assistant, 100% local, sem nada instalado no console além do dashboard que você já usa.

Tudo sai do FTP do dashboard (UnleashX, XBMC, Avalaunch, EvoX) e da HTTP API do XBMC. Os comandos `SITE` usados foram mapeados por engenharia reversa do UnleashX 0.37.1218A.

## O que aparece no HA

| Plataforma | Entidades |
|---|---|
| Media player | estado (desligado / dashboard / jogando), jogo atual com capa, **abrir jogo/app** (`select_source`, `play_media`), biblioteca navegável com capas, desligar; no XBMC: play/pausa/parar/próxima/anterior/volume/mudo/seek |
| Sensores | atividade, jogo atual, último jogo, última sessão (min), nº de jogos / apps / saves, espaço livre e uso (%) de C, E, F, G, X, Y, Z, versão do dashboard; no XBMC: temperatura da GPU/CPU, ventoinha, memória livre, tela do XBMC, versão do XBMC |
| Botões | reiniciar, desligar, reinício completo, abrir/fechar bandeja, reiniciar rede, reiniciar FTP, recarregar dashboard, dashboard Microsoft, backup dos saves, atualizar biblioteca |
| Selects | abrir jogo, abrir aplicativo |
| Switches (Config.xml) | sincronizar relógio (SNTP), abrir jogo/DVD/CD/dados ao inserir, notícias, widescreen, 1080i, Fahrenheit |
| Números (Config.xml) | proteção de tela, desligamento automático |
| Imagem | capa do jogo atual (ou do último) |
| Câmera | screenshot da tela (XBMC) |
| Remote | botões do controle (`cima`, `baixo`, `esquerda`, `direita`, `a`/`ok`, `b`/`voltar`, `x`, `y`, `preto`, `branco`, `lt`, `rt`, `start`, `back`) via XBMC |
| Binários | dashboard (FTP), rede (ping) e **travado** (app congelado: ping responde, porta 21 muda por 5 min depois do XBMC) |

### Serviços
`xbox_classico.executar`, `comando_site` (resposta), `xbmc_comando` (resposta), `enviar_arquivo`, `baixar_arquivo`, `listar` (resposta), `backup_saves` (zip em `/config/backups/xbox_classico/`), `atualizar_biblioteca`.

## Requisitos
- FTP do dashboard ligado (UnleashX: `xbox`/`xbox` por padrão).
- Para telemetria/controle de mídia no XBMC: `<webserver>true</webserver>` em `F:\Apps\XBMC\UserData\guisettings.xml`.
- IP fixo para o Xbox (reserva DHCP no roteador).

## Como funciona
- **Estado**: a cada 15 s o HA conecta no FTP; o banner diz qual app está aberto (`UnleashX` / `FileZilla (XBMC)` / ...). Sem FTP, um ping diferencia *em jogo* de *desligado* quando o jogo mantém a rede ativa; jogos abertos pelo HA ficam marcados até o dashboard voltar.
- **Abrir jogos**: `SITE EXEC <xbe>` no UnleashX; `XBMC.RunXBE()` no XBMC. Depois de qualquer comando que fecha o app o HA fica 25 s sem consultar o console (o XBMC 2.0 trava se for consultado enquanto fecha). Se mesmo assim ele congelar (ping ok, FTP mudo), a atividade vira `travado` em 5 min — só religando no botão.
- **Discos**: `SITE DRIVESTAT` (comando oculto do UnleashX) devolve usado/livre/total de todas as partições.
- **Biblioteca**: varre `E:/F:/G:\Games`, `HDDLoader` e `Apps` (um nível a mais para pastas como `Emulators`), lê o cabeçalho de cada XBE (título, title ID) e a capa (`TitleImage.xbx` ou a seção `$$XTIMAGE` do XBE, DXT1 → PNG).
- **Config.xml**: editado no lugar (só o valor muda), com backup em `C:\Config.xml.ha-backup` na primeira escrita; o dashboard é recarregado para aplicar.

### Comandos SITE do UnleashX 0.37 (RE)
`REBOOT`, `RESTART`, `SHUTDOWN`, `POWERCYCLE`, `FTPRESET`, `FTPSTOP`, `NETRESET`, `TRAYOPEN`/`EJECT`, `TRAYCLOSE`, `DRIVESTAT`, `EXEC <xbe>`, `LAUNCH <xbe>`, `MD5 <arquivo>`, `XBERENAME`, `FREESPACE <drive>`, `FREEROOTSPACEDISABLE`, `TITLES`, `TITLEIMAGE`, `MAKE_FILE_TREE`.

## Testes
```
uv run --with pillow --with pytest pytest -q tests
```
