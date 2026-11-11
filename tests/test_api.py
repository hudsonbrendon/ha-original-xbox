"""Testes dos parsers (sem Home Assistant): uv run --with pillow --with pytest pytest -q"""

import io
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "xbox_classico"))

import api  # noqa: E402

DRIVESTAT = (
    "200 C\t Used: 187,30MB\tFree: 312,63MB\tTotal: 499,92MB\t\tD\t Used: 0,00MB\tFree: 0,00MB\tTotal: 0,00MB"
    "\t\tE\t Used: 4.321,97MB\tFree: 559,66MB\tTotal: 4.881,63MB\t\tF\t Used: 27.796,70MB\tFree: 3.767,92MB"
    "\tTotal: 31.564,63MB"
)

CONFIG = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n<UnleashX>\r\n\t<Settings>\r\n'
    '\t\t<Network Enable="Yes" Type="DHCP">\r\n\t\t</Network>\r\n'
    '\t\t<FTP Enable="Yes">\r\n\t\t\t<MaxUsers>2</MaxUsers>\r\n\t\t</FTP>\r\n'
    '\t\t<Newsfeed Enable="Yes" Interval="30">\r\n\t\t</Newsfeed>\r\n'
    '\t\t<Preference>\r\n\t\t\t<Games AutoLaunch="Yes">C:\\xboxdash.xbe</Games>\r\n'
    '\t\t\t<DVD AutoLaunch="Yes">F:\\Apps\\DVDX2\\default.xbe</DVD>\r\n'
    '\t\t\t<SNTP Synchronize="No">216.244.192.3</SNTP>\r\n\t\t\t<FanSpeed>2.00</FanSpeed>\r\n'
    '\t\t\t<ScreenSaver Wait="240">\r\n\t\t\t</ScreenSaver>\r\n\t\t\t<AutoTurnOff>0</AutoTurnOff>\r\n'
    '\t\t\t<VideoSettings Widescreen="Yes" FastRefresh="Yes" Use1080I="Yes"></VideoSettings>\r\n'
    "\t\t\t<UseFahrenheit>No</UseFahrenheit>\r\n\t\t</Preference>\r\n\t</Settings>\r\n</UnleashX>\r\n"
)


def test_drivestat():
    d = api.parse_drivestat(DRIVESTAT)
    assert set(d) == {"C", "E", "F"}  # D (DVD) com total 0 some
    assert d["E"] == {"used": 4321.97, "free": 559.66, "total": 4881.63}
    assert d["F"]["total"] == 31564.63


def test_numbers_both_locales():
    assert api.parse_number("4.321,97") == 4321.97
    assert api.parse_number("4,321.97") == 4321.97
    assert api.parse_number("187.30") == 187.3
    assert api.parse_number("1.000") == 1000.0


def test_banner():
    assert api.app_from_banner("220 UnleashX FTP ready.") == api.APP_DASHBOARD
    assert api.app_from_banner("220-FileZilla Server version 0.9.11 beta") == api.APP_XBMC
    assert api.app_from_banner("220 Welcome") == api.APP_OTHER


def test_paths():
    assert api.to_ftp_path("F:\\Games\\Halo 2\\default.xbe") == "/F/Games/Halo 2/default.xbe"
    assert api.to_xbox_path("/F/Games/Halo 2/default.xbe") == "F:\\Games\\Halo 2\\default.xbe"
    assert api.to_xbox_path("C:\\x.xbe") == "C:\\x.xbe"


def test_list():
    lines = [
        "drw-r--r--   1 XBOX      XBOX        0 Nov 15 08:00 ..",
        "drw-r--r--   1 XBOX      XBOX        0 Nov 15 10:44 Halo 2",
        "-rw-r--r--   1 XBOX      XBOX        4041 Nov 15 08:02 Config.xml",
    ]
    assert api.parse_list(lines) == [api.Entry("Halo 2", True, 0), api.Entry("Config.xml", False, 4041)]


def test_config_roundtrip_keeps_layout():
    cfg = api.parse_config(CONFIG)
    assert cfg["sntp"] is False and cfg["autolaunch_dvd"] is True and cfg["screensaver_wait"] == 240
    assert cfg["dvd_launch"] == "F:\\Apps\\DVDX2\\default.xbe" and cfg["network_type"] == "DHCP"
    new = api.set_config(CONFIG, "sntp", True)
    new = api.set_config(new, "sntp_server", "200.160.0.8")
    new = api.set_config(new, "auto_turn_off", 60)
    new = api.set_config(new, "use_1080i", False)
    out = api.parse_config(new)
    assert out["sntp"] and out["sntp_server"] == "200.160.0.8" and out["auto_turn_off"] == 60 and not out["use_1080i"]
    assert out["widescreen"] is True  # vizinho no mesmo elemento intacto
    assert new.count("\r\n") == CONFIG.count("\r\n") and len(new) - len(CONFIG) < 10


def _xbe(title: str, tid: int, image: bytes | None) -> bytes:
    base = 0x10000
    data = bytearray(0x3000)
    data[:4] = b"XBEH"
    struct.pack_into("<I", data, 0x104, base)
    cert = 0x200
    struct.pack_into("<I", data, 0x118, base + cert)
    struct.pack_into("<I", data, cert + 8, tid)
    t = title.encode("utf-16-le")
    data[cert + 0xC : cert + 0xC + len(t)] = t
    sec, name = 0x400, 0x600
    struct.pack_into("<II", data, 0x11C, 1, base + sec)
    data[name : name + 10] = b"$$XTIMAGE\0"
    if image:
        struct.pack_into("<IIIIII", data, sec, 0, 0, 0, 0x1000, len(image), base + name)
        data[0x1000 : 0x1000 + len(image)] = image
    return bytes(data)


def _xpr_dxt1(w=16, h=16) -> bytes:
    hdr = 0x800
    fmt = (0x0C << 8) | ((w.bit_length() - 1) << 20) | ((h.bit_length() - 1) << 24)
    blk = struct.pack("<HHI", 0xF800, 0xF800, 0)  # bloco vermelho
    data = bytearray(hdr) + blk * ((w // 4) * (h // 4))
    data[:4] = b"XPR0"
    struct.pack_into("<II", data, 4, len(data), hdr)
    struct.pack_into("<I", data, 0x18, fmt)
    return bytes(data)


def test_xbe_and_cover():
    from PIL import Image

    img = _xpr_dxt1()
    xbe = _xbe("Halo 2", 0x4D530064, img)
    info = api.parse_xbe(xbe)
    assert (info.title, info.title_id, info.image_offset, info.image_size) == ("Halo 2", "4d530064", 0x1000, len(img))
    png = api.xpr_to_png(xbe[info.image_offset : info.image_offset + info.image_size])
    pic = Image.open(io.BytesIO(png))
    assert pic.size == (16, 16) and pic.getpixel((0, 0))[:3] == (255, 0, 0)


def test_title_meta():
    assert api.parse_title_meta("\ufeffTitleName=Halo 2\r\n".encode("utf-16-le")) == "Halo 2"


def test_xbmc_parsers():
    html = "<html>\n<li>Filename:F:\\Music\\a.mp3\n<li>PlayStatus:Paused\n<li>Time:01:02\n<li>Duration:03:04:05</html>"
    kv = api.parse_kv(api.strip_html(html))
    assert kv["PlayStatus"] == "Paused" and kv["Filename"] == "F:\\Music\\a.mp3"
    assert api.parse_duration(kv["Time"]) == 62 and api.parse_duration(kv["Duration"]) == 11045
    assert api.parse_temp("GPU: 43°C") == 43.0 and api.parse_temp("CPU: Unknown") is None
    assert api.parse_temp("GPU: 109°F") == 42.8
    assert api.parse_first_number("Fan Speed: 40%") == 40.0 and api.parse_first_number("32MB") == 32.0


def test_offline_activity():
    f = api.offline_activity
    # XBMC some com porta muda + ping: segura como xbmc, vira travado após 5 min
    assert f("xbmc", True, True, False, None, 1000) == ("xbmc", 1000)
    assert f("xbmc", True, True, False, 1000, 1200) == ("xbmc", 1000)
    assert f("xbmc", True, True, False, 1000, 1300) == ("travado", 1000)
    assert f("travado", True, True, False, 1000, 5000) == ("travado", 1000)
    # vindo do dashboard (jogo aberto pelo controle) nunca vira travado
    assert f("dashboard", True, True, False, None, 1000) == ("jogo", None)
    # porta recusando / sem ping
    assert f("xbmc", False, True, False, 1000, 2000) == ("jogo", None)
    assert f("xbmc", True, False, False, 1000, 2000) == ("desligado", None)
    assert f(None, False, False, True, None, 0) == ("jogo", None)
    assert f("dashboard", False, False, False, None, 0) == ("desligado", None)


def test_script_output_and_source():
    text = (
        "nonce=ab12cd34\nsystem.cputemperature=56°C\nsystem.gputemperature=41°C\nsystem.fanspeed=40%\n"
        "system.hddtemperature=Ocupado\nsystem.freememory=33MB\nsystem.currentwindow=Programas\n"
        "system.uptime=14 Minutos\nsystem.buildversion=3.6-DEV-r33046\nplayer.title=\n"
        "system.xboxversion=v1.6\nsystem.bios=Evox M8 Plus (1.6) \n"
    )
    raw = "nonce=x\r\nwindow.id=10001\r\nsystem.cputemperature=58\u00b0C\r\nsystem.currentwindow=\r\n".encode()
    w = api.parse_script_output(raw.decode("utf-8"))
    assert w["cpu_temp"] == 58.0 and w["window"] == "Programas" and w["playing"] is None
    t = "nonce=y\nplayer.playing=1\nplayer.paused=1\nplayer.title=\nplayer.file=F:\\Music\\teste-ha.wav\nplayer.time_s=5\nplayer.total_s=90\n"
    p = api.parse_script_output(t)["playing"]
    assert p["Title"] == "teste-ha.wav" and p["Time"] == "00:05" and p["Duration"] == "01:30" and p["PlayStatus"] == "Paused"
    assert api.parse_duration(p["Duration"]) == 90
    d = api.parse_script_output(text)
    assert d["nonce"] == "ab12cd34" and d["cpu_temp"] == 56.0 and d["gpu_temp"] == 41.0 and d["fan"] == 40.0
    assert d["hdd_temp"] is None and d["free_memory"] == 33.0 and d["window"] == "Programas"
    assert d["xbox_version"] == "v1.6" and d["bios"] == "Evox M8 Plus (1.6)" and d["playing"] is None
    src = api.XBMC_SCRIPT
    compile(src.replace("\r\n", "\n"), "ha_info.py", "exec")  # sintaxe válida (sem f-strings)
    assert "E:\\\\TDATA\\\\ha_xbox_classico\\\\ha_info.txt" in src and f"v{api.SCRIPT_VERSION} " in src


def test_fatx_names():
    assert api.fatx_ok("default.xbe") and api.fatx_ok("x" * 42)
    assert not api.fatx_ok("Alone in the Dark - New Nightmare D1 (E).txt")  # 44
    assert not api.fatx_ok("a:b.txt") and not api.fatx_ok("é.txt") and not api.fatx_ok("")
