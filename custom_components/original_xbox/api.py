r"""Client for a modded original Xbox over the dashboard FTP (UnleashX/XBMC/Avalaunch).

No Home Assistant dependencies: everything is synchronous (ftplib) and runs in an executor.
SITE commands found by reverse engineering UnleashX 0.37.1218A (C:\evoxdash.xbe):
REBOOT, RESTART, SHUTDOWN, POWERCYCLE, FTPRESET, FTPSTOP, NETRESET, TRAYOPEN/EJECT,
TRAYCLOSE, DRIVESTAT, EXEC/LAUNCH <xbe>, MD5 <file>, XBERENAME, FREESPACE <drive>.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import ftplib
import io
import posixpath
import re
import socket
import struct
import threading

TIMEOUT = 8

APP_DASHBOARD = "unleashx"
APP_XBMC = "xbmc"
APP_AVALAUNCH = "avalaunch"
APP_EVOX = "evox"
APP_OTHER = "other"


class XboxError(Exception):
    """Failure talking to the Xbox."""


class XboxOffline(XboxError):
    """No FTP: console off, in a game or off the network."""


class XboxHung(XboxOffline):
    """Port 21 silent (timeout, not refused): connection with no banner or unanswered SYN.

    With ping answering and coming from XBMC, this is the XBMC 2.0 freeze (seen on 2026-11-11).
    """


@dataclass(frozen=True)
class Entry:
    name: str
    is_dir: bool
    size: int


FTP_APPS = ("xbmc", "avalaunch", "evox", "other_app", "frozen")
HUNG_AFTER_SECONDS = 300


def offline_activity(
    prev: str | None, silent: bool, ping: bool, launched: bool, silent_since: float | None, now: float
) -> tuple[str, float | None]:
    """Activity while the FTP is down -> (activity, silent_since).

    silent = port 21 silent (timeout, not refused). Frozen only when coming from an app with FTP
    (XBMC & co.), ping answers and the silence lasts HUNG_AFTER_SECONDS; until then keep the app.
    """
    if silent and ping and prev in FTP_APPS:
        silent_since = silent_since or now
        if now - silent_since >= HUNG_AFTER_SECONDS:
            return "frozen", silent_since
        return prev, silent_since
    if launched or ping:
        return "game", None
    return "off", None


FATX_MAX_NAME = 42
_FATX_BAD = re.compile(r'[<>:"|*?\\/]|[^\x20-\x7e]')


def fatx_ok(name: str) -> bool:
    r"""Xbox FATX accepts names of up to 42 printable ASCII characters, without <>:"|*?\/."""
    return 0 < len(name) <= FATX_MAX_NAME and not _FATX_BAD.search(name)


def app_from_banner(banner: str) -> str:
    low = banner.lower()
    if "unleashx" in low:
        return APP_DASHBOARD
    if "filezilla" in low or "xbmc" in low or "xbox media center" in low:
        return APP_XBMC
    if "avalaunch" in low:
        return APP_AVALAUNCH
    if "evox" in low:
        return APP_EVOX
    return APP_OTHER


def parse_number(text: str) -> float:
    """'4.321,97' / '4,321.97' / '187,30' / '187.30' -> float."""
    text = text.strip()
    m = re.search(r"[.,](\d{1,2})$", text)
    if m:
        whole = re.sub(r"[.,]", "", text[: m.start()])
        return float(f"{whole}.{m.group(1)}")
    return float(re.sub(r"[.,]", "", text))


def parse_drivestat(reply: str) -> dict[str, dict[str, float]]:
    r"""'200 C\t Used: 187,30MB\tFree: 312,63MB\tTotal: 499,92MB\t\tD ...' -> MB per drive."""
    body = reply[4:] if reply[:3].isdigit() else reply
    drives: dict[str, dict[str, float]] = {}
    for m in re.finditer(
        r"([A-Z])\s+Used:\s*([\d.,]+)\s*MB\s+Free:\s*([\d.,]+)\s*MB\s+Total:\s*([\d.,]+)\s*MB", body
    ):
        total = parse_number(m.group(4))
        if total <= 0:
            continue
        drives[m.group(1)] = {
            "used": parse_number(m.group(2)),
            "free": parse_number(m.group(3)),
            "total": total,
        }
    return drives


def parse_list(lines: list[str]) -> list[Entry]:
    out = []
    for line in lines:
        parts = line.split(None, 8)
        if len(parts) < 9 or parts[8] in (".", ".."):
            continue
        try:
            size = int(parts[4])
        except ValueError:
            size = 0
        out.append(Entry(parts[8], line.startswith("d"), size))
    return out


def to_ftp_path(path: str) -> str:
    r"""'F:\Games\Halo 2\default.xbe' -> '/F/Games/Halo 2/default.xbe'."""
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = "/" + path[0].upper() + path[2:]
    return path if path.startswith("/") else "/" + path


def to_xbox_path(path: str) -> str:
    r"""'/F/Games/Halo 2/default.xbe' -> 'F:\Games\Halo 2\default.xbe'."""
    if len(path) >= 2 and path[1] == ":":
        return path.replace("/", "\\")
    parts = path.strip("/").split("/")
    return parts[0].upper() + ":\\" + "\\".join(parts[1:])


# ---------------------------------------------------------------- XBE / XPR


@dataclass(frozen=True)
class XbeInfo:
    title: str
    title_id: str
    region: int
    version: int
    image_offset: int | None  # $$XTIMAG section in the file
    image_size: int


XBE_HEADER_READ = 0x4000


def parse_xbe(data: bytes) -> XbeInfo:
    if data[:4] != b"XBEH":
        raise XboxError("not an XBE")

    def u32(off: int) -> int:
        return struct.unpack_from("<I", data, off)[0]

    base = u32(0x104)
    cert = u32(0x118) - base
    title = data[cert + 0xC : cert + 0xC + 80].decode("utf-16-le", "replace").split("\0")[0].strip()
    title_id = f"{u32(cert + 8):08x}"
    region = u32(cert + 0xA0)
    version = u32(cert + 0xAC)
    image_offset, image_size = None, 0
    nsec, sec = u32(0x11C), u32(0x120) - base
    for i in range(nsec):
        off = sec + i * 0x38
        if off + 0x38 > len(data):
            break
        name_ptr = u32(off + 0x14) - base
        if not 0 <= name_ptr < len(data):
            continue
        name = data[name_ptr : data.find(b"\0", name_ptr)]
        if name.startswith(b"$$XTIMAG"):
            image_offset, image_size = u32(off + 0xC), u32(off + 0x10)
    return XbeInfo(title, title_id, region, version, image_offset, image_size)


_BCN = {0x0C: (1, 8), 0x0E: (2, 16), 0x0F: (3, 16)}  # D3DFMT_DXT1/DXT3/DXT5 -> (bcn, bytes/block)


def xpr_to_png(data: bytes) -> bytes | None:
    """TitleImage.xbx / $$XTIMAGE (XPR0 with a DXT texture) -> PNG. None if the format is not DXT."""
    if data[:4] != b"XPR0":
        return None
    from PIL import Image  # Pillow ships with HA

    header = struct.unpack_from("<I", data, 8)[0]
    fmt = struct.unpack_from("<I", data, 0x18)[0]
    kind = (fmt >> 8) & 0xFF
    if kind not in _BCN:
        return None
    w, h = 1 << ((fmt >> 20) & 0xF), 1 << ((fmt >> 24) & 0xF)
    bcn, block = _BCN[kind]
    size = max(1, w // 4) * max(1, h // 4) * block
    pixels = data[header : header + size]
    if len(pixels) < size:
        return None
    img = Image.frombytes("RGBA", (w, h), pixels, "bcn", bcn)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def parse_title_meta(data: bytes) -> str | None:
    """TitleMeta.xbx (UTF-16, 'TitleName=Halo 2')."""
    text = data.decode("utf-16", "replace")
    m = re.search(r"TitleName=([^\r\n]+)", text)
    return m.group(1).strip() if m else None


# ---------------------------------------------------------------- UnleashX Config.xml

# key -> (regex with 1 value group, type)
CONFIG_FIELDS: dict[str, tuple[str, str]] = {
    "sntp": (r'<SNTP Synchronize="(\w+)"', "bool"),
    "sntp_server": (r'<SNTP Synchronize="\w+">([^<]*)<', "str"),
    "autolaunch_games": (r'<Games AutoLaunch="(\w+)"', "bool"),
    "autolaunch_dvd": (r'<DVD AutoLaunch="(\w+)"', "bool"),
    "autolaunch_audiocd": (r'<AudioCD AutoLaunch="(\w+)"', "bool"),
    "autolaunch_data": (r'<Data AutoLaunch="(\w+)"', "bool"),
    "newsfeed": (r'<Newsfeed Enable="(\w+)"', "bool"),
    "screensaver_wait": (r'<ScreenSaver Wait="(\d+)"', "int"),
    "auto_turn_off": (r"<AutoTurnOff>(\d+)</AutoTurnOff>", "int"),
    "widescreen": (r'<VideoSettings[^>]*\bWidescreen="(\w+)"', "bool"),
    "use_1080i": (r'<VideoSettings[^>]*\bUse1080I="(\w+)"', "bool"),
    "fahrenheit": (r"<UseFahrenheit>(\w+)</UseFahrenheit>", "bool"),
    "network_type": (r'<Network Enable="\w+" Type="(\w+)"', "str"),
    "ftp_max_users": (r"<MaxUsers>(\d+)</MaxUsers>", "int"),
    "fan_speed": (r"<FanSpeed>([\d.]+)</FanSpeed>", "str"),
    "dvd_launch": (r'<DVD AutoLaunch="\w+">([^<]*)<', "str"),
}

_TRUE = {"yes", "true", "1", "on"}


def parse_config(text: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, (pattern, kind) in CONFIG_FIELDS.items():
        m = re.search(pattern, text)
        if not m:
            continue
        raw = m.group(1)
        if kind == "bool":
            out[key] = raw.lower() in _TRUE
        elif kind == "int":
            out[key] = int(raw)
        else:
            out[key] = raw
    return out


def set_config(text: str, key: str, value: object) -> str:
    """Replace only the field value, keeping the rest of the file (layout, CRLF)."""
    pattern, kind = CONFIG_FIELDS[key]
    m = re.search(pattern, text)
    if not m:
        raise XboxError(f"field {key} does not exist in Config.xml")
    old = m.group(1)
    if kind == "bool":
        # keep the file style (Yes/No or True/False)
        new = ("True" if value else "False") if old.lower() in ("true", "false") else ("Yes" if value else "No")
    else:
        new = str(value)
    return text[: m.start(1)] + new + text[m.end(1) :]


# ---------------------------------------------------------------- FTP client


class XboxClient:
    """One connection per operation (UnleashX accepts few users); serialized by a lock."""

    def __init__(self, host: str, username: str = "xbox", password: str = "xbox", port: int = 21) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self._lock = threading.Lock()

    @contextmanager
    def session(self) -> Iterator[ftplib.FTP]:
        with self._lock:
            ftp = ftplib.FTP(timeout=TIMEOUT, encoding="latin-1")
            try:
                ftp.connect(self.host, self.port)
            except (OSError, EOFError) as err:
                # timeout (connected with no banner or unanswered SYN) != refused (port closed)
                hung = isinstance(err, TimeoutError)
                ftp.close()
                raise (XboxHung if hung else XboxOffline)(str(err)) from err
            try:
                ftp.login(self.username, self.password)
                yield ftp
            except ftplib.error_perm as err:
                raise XboxError(str(err)) from err
            except (OSError, EOFError, ftplib.Error) as err:
                raise XboxError(str(err)) from err
            finally:
                try:
                    ftp.quit()
                except Exception:  # always close
                    ftp.close()

    def probe(self) -> dict[str, str]:
        """Banner + SYST. Raises XboxOffline if the FTP does not answer."""
        with self.session() as ftp:
            banner = ftp.getwelcome()
            try:
                syst = ftp.sendcmd("SYST")
            except ftplib.Error:
                syst = ""
        return {"banner": banner, "system": syst[4:] if syst[:3].isdigit() else syst, "app": app_from_banner(banner + " " + syst)}

    def site(self, command: str) -> str:
        with self.session() as ftp:
            return ftp.sendcmd(f"SITE {command}")

    def site_fire(self, command: str) -> str:
        """Power SITE command: UnleashX runs it and sometimes answers 502 or drops the connection.

        POWERCYCLE falls through to the end of the handler. Only a real failure if it never connected.
        """
        try:
            return self.site(command)
        except XboxOffline:
            raise
        except XboxError as err:
            return f"sent ({err})"

    def drivestat(self) -> dict[str, dict[str, float]]:
        return parse_drivestat(self.site("DRIVESTAT"))

    def md5(self, xbox_path: str) -> str | None:
        try:
            reply = self.site(f"MD5 {xbox_path}")
        except XboxError:
            return None
        m = re.search(r"([0-9a-f]{32})", reply)
        return m.group(1) if m else None

    def execute(self, xbox_path: str) -> str:
        # EXEC really answers 200/550 before switching XBE: here the error matters
        try:
            return self.site(f"EXEC {xbox_path}")
        except XboxOffline:
            raise
        except XboxError as err:
            if "does not exist" in str(err) or "Failed" in str(err):
                raise
            return f"sent ({err})"

    def listdir(self, path: str) -> list[Entry]:
        # LIST with a full path hangs UnleashX: always CWD + LIST
        with self.session() as ftp:
            return self._listdir(ftp, path)

    @staticmethod
    def _listdir(ftp: ftplib.FTP, path: str) -> list[Entry]:
        lines: list[str] = []
        try:
            ftp.cwd(to_ftp_path(path))
        except ftplib.error_perm:
            return []
        ftp.retrlines("LIST", lines.append)
        return parse_list(lines)

    def read(self, path: str, size: int | None = None, offset: int = 0) -> bytes:
        with self.session() as ftp:
            return self._read(ftp, path, size, offset)

    @staticmethod
    def _read(ftp: ftplib.FTP, path: str, size: int | None = None, offset: int = 0) -> bytes:
        buf = bytearray()
        ftp_path = to_ftp_path(path)
        if size is None:
            ftp.retrbinary(f"RETR {ftp_path}", buf.extend, rest=offset or None)
            return bytes(buf)
        # partial read: open the data channel by hand and cut it once the size is reached
        ftp.voidcmd("TYPE I")
        conn = ftp.transfercmd(f"RETR {ftp_path}", rest=offset or None)
        try:
            while len(buf) < size:
                chunk = conn.recv(min(65536, size - len(buf)))
                if not chunk:
                    break
                buf.extend(chunk)
        finally:
            conn.close()
        try:
            ftp.voidresp()
        except (ftplib.Error, OSError, EOFError):
            pass  # 426/abort expected when we cut the transfer
        return bytes(buf)

    def write(self, path: str, data: bytes) -> None:
        with self.session() as ftp:
            ftp.storbinary(f"STOR {to_ftp_path(path)}", io.BytesIO(data))

    def mkdirs(self, path: str) -> None:
        with self.session() as ftp:
            cur = ""
            for part in to_ftp_path(path).strip("/").split("/"):
                cur += "/" + part
                try:
                    ftp.mkd(cur)
                except ftplib.error_perm:
                    pass

    # ------------------------------------------------------------ high level

    def xbe_info(self, path: str) -> XbeInfo:
        return parse_xbe(self.read(path, XBE_HEADER_READ))

    def title_image(self, title_id: str, xbe_path: str | None = None) -> bytes | None:
        """Cover PNG: TitleImage.xbx saved by the dashboard, else the XBE $$XTIMAGE section."""
        with self.session() as ftp:
            for folder in ("E:\\UDATA", "E:\\TDATA"):
                try:
                    data = self._read(ftp, f"{folder}\\{title_id}\\TitleImage.xbx")
                except ftplib.Error:
                    continue
                png = xpr_to_png(data)
                if png:
                    return png
            if xbe_path:
                info = parse_xbe(self._read(ftp, xbe_path, XBE_HEADER_READ))
                if info.image_offset and 0 < info.image_size < 2_000_000:
                    return xpr_to_png(self._read(ftp, xbe_path, info.image_size, info.image_offset))
        return None

    def scan_library(self, roots: list[tuple[str, str]], known: dict[str, dict]) -> list[dict]:
        r"""Scan roots = [(category, 'F:\Games'), ...] for items.

        Folders with an .xbe become items; folders without one (e.g. F:\Apps\Emulators) are
        opened one more level. `known` avoids re-reading an unchanged XBE.
        """
        items: list[dict] = []
        with self.session() as ftp:
            for category, root in roots:
                for entry in self._listdir(ftp, root):
                    if not entry.is_dir:
                        continue
                    folder = f"{root.rstrip(chr(92))}\\{entry.name}"
                    found = self._scan_folder(ftp, category, folder, known)
                    if found:
                        items.append(found)
                        continue
                    for sub in self._listdir(ftp, folder):
                        if sub.is_dir:
                            found = self._scan_folder(ftp, category, f"{folder}\\{sub.name}", known)
                            if found:
                                items.append(found)
        return items

    def _scan_folder(self, ftp: ftplib.FTP, category: str, folder: str, known: dict[str, dict]) -> dict | None:
        files = [e for e in self._listdir(ftp, folder) if not e.is_dir and e.name.lower().endswith(".xbe")]
        if not files:
            return None
        main = next((e for e in files if e.name.lower() == "default.xbe"), None) or next(
            (e for e in files if e.name.lower() == "evoxdash.xbe"), files[0]
        )
        path = f"{folder}\\{main.name}"
        cached = known.get(path)
        if cached and cached.get("size") == main.size:
            return {**cached, "category": category}
        try:
            info = parse_xbe(self._read(ftp, path, XBE_HEADER_READ))
            title, tid, region = info.title or posixpath.basename(folder), info.title_id, info.region
        except (XboxError, ftplib.Error, struct.error, IndexError):
            title, tid, region = folder.rsplit("\\", 1)[-1], None, 0
        return {
            "name": title,
            "folder": folder.rsplit("\\", 1)[-1],
            "path": path,
            "title_id": tid,
            "region": region,
            "size": main.size,
            "category": category,
        }

    def saves(self) -> list[dict]:
        r"""Saves in E:\UDATA: game name from TitleMeta.xbx and number of slots."""
        out = []
        with self.session() as ftp:
            for entry in self._listdir(ftp, "E:\\UDATA"):
                if not entry.is_dir:
                    continue
                folder = f"E:\\UDATA\\{entry.name}"
                children = self._listdir(ftp, folder)
                name = None
                if any(c.name.lower() == "titlemeta.xbx" for c in children):
                    try:
                        name = parse_title_meta(self._read(ftp, f"{folder}\\TitleMeta.xbx"))
                    except ftplib.Error:
                        name = None
                out.append(
                    {"title_id": entry.name.lower(), "name": name or entry.name, "slots": sum(c.is_dir for c in children)}
                )
        return out

    def upload_tree(self, local_dir: str, remote_dir: str, progress=None) -> tuple[int, int, list[str]]:
        """Upload a whole local folder (e.g. a game) to remote_dir.

        Names FATX does not accept are skipped. Returns (files, bytes, skipped).
        """
        import os

        files = total = 0
        skipped: list[str] = []
        base = to_ftp_path(remote_dir).rstrip("/")
        with self.session() as ftp:
            for root, dirs, names in os.walk(local_dir):
                for d in [d for d in dirs if not fatx_ok(d)]:
                    skipped.append(os.path.relpath(os.path.join(root, d), local_dir) + "/")
                    dirs.remove(d)
                dirs.sort()
                rel = os.path.relpath(root, local_dir)
                target = base if rel == "." else f"{base}/{rel.replace(os.sep, '/')}"
                cur = ""
                for part in target.strip("/").split("/"):
                    cur += "/" + part
                    try:
                        ftp.mkd(cur)
                    except ftplib.error_perm:
                        pass
                for name in sorted(names):
                    path = os.path.join(root, name)
                    if not fatx_ok(name):
                        skipped.append(os.path.relpath(path, local_dir))
                        continue
                    with open(path, "rb") as f:
                        ftp.storbinary(f"STOR {target}/{name}", f, blocksize=65536)
                    files += 1
                    total += os.path.getsize(path)
                    if progress:
                        progress(files, total, f"{target}/{name}")
        return files, total, skipped

    # ------------------------------------------------------------ XBMC telemetry without HTTP

    def ensure_script(self) -> bool:
        """Install/update ha_info.py (only from UnleashX: the XBMC FTP refuses absolute paths)."""
        try:
            current = self.read(SCRIPT_PATH, 120).decode("latin-1")
        except XboxError:
            current = ""
        if f"v{SCRIPT_VERSION} " in current:
            return False
        self.mkdirs(SCRIPT_DIR)
        self.write(SCRIPT_PATH, XBMC_SCRIPT.encode("ascii"))
        return True

    def run_xbmc_script(self, full: bool = False, wait: float | None = None) -> dict:
        """SITE RunScript on the XBMC FTP and wait for the output with the same nonce."""
        import secrets
        import time

        nonce = secrets.token_hex(4)
        self.site(f"RunScript({SCRIPT_PATH},{nonce},{'full' if full else 'fast'})")
        deadline = time.monotonic() + (wait or (90.0 if full else 25.0))
        while time.monotonic() < deadline:
            time.sleep(1.5)
            try:
                data = parse_script_output(self.read(SCRIPT_OUT).decode("utf-8", "replace"))
            except XboxError:
                continue
            if data["nonce"] == nonce:
                return data
        raise XboxError("the telemetry script did not answer (XBMC busy?)")

    def download_tree(self, path: str, sink) -> int:
        """Download recursively, calling sink(relative_path, bytes). Returns the number of files."""
        count = 0
        with self.session() as ftp:
            stack = [("", path)]
            while stack:
                rel, cur = stack.pop()
                for e in self._listdir(ftp, cur):
                    child = f"{cur}\\{e.name}"
                    crel = f"{rel}/{e.name}" if rel else e.name
                    if e.is_dir:
                        stack.append((crel, child))
                    else:
                        sink(crel, self._read(ftp, child))
                        count += 1
        return count


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------- XBMC (XBMC 2.x HTTP API)

# button codes from the XBMC 2.x keymap (SendKey)
XBMC_KEYS = {
    "a": 256, "ok": 256, "b": 257, "x": 258, "y": 259, "black": 260, "white": 261,
    "lt": 262, "rt": 263, "l3": 264, "r3": 265,
    "up": 270, "down": 271, "left": 272, "right": 273, "start": 274, "back": 275,
}


def strip_html(text: str) -> list[str]:
    r"""'<html><li>Filename:x\n<li>Title:y</html>' -> ['Filename:x', 'Title:y']."""
    text = re.sub(r"<li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_kv(lines: list[str]) -> dict[str, str]:
    out = {}
    for line in lines:
        key, sep, value = line.partition(":")
        if sep:
            out[key.strip()] = value.strip()
    return out


def parse_temp(text: str) -> float | None:
    m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*°?\s*([CF])", text)
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return round((value - 32) * 5 / 9, 1) if m.group(2) == "F" else value


def parse_first_number(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", text.partition(":")[2] or text)
    return float(m.group(1).replace(",", ".")) if m else None


def parse_duration(text: str | None) -> int | None:
    """'01:02:03' / '02:03' -> seconds."""
    if not text or not re.fullmatch(r"\d+(?::\d+){1,2}", text):
        return None
    secs = 0
    for part in text.split(":"):
        secs = secs * 60 + int(part)
    return secs


class XbmcClient:
    """XBMC HTTP API (needs <webserver>true</webserver> in guisettings.xml)."""

    def __init__(self, host: str, port: int = 80) -> None:
        self.base = f"http://{host}:{port}/xbmcCmds/xbmcHttp"

    def cmd(self, command: str, parameter: str | None = None, timeout: float = 6) -> str:
        from urllib.parse import quote
        from urllib.request import urlopen

        url = f"{self.base}?command={quote(command)}"
        if parameter is not None:
            url += "&parameter=" + quote(parameter, safe=":;\\(),.")
        try:
            with urlopen(url, timeout=timeout) as resp:  # LAN only
                return resp.read().decode("utf-8", "replace")
        except Exception as err:  # http.client raises HTTPException, not OSError
            raise XboxError(f"XBMC: {err!r}") from err

    def lines(self, command: str, parameter: str | None = None) -> list[str]:
        return strip_html(self.cmd(command, parameter))

    def status(self, with_system: bool = True) -> dict:
        """XBMC state. with_system=False skips the 5 telemetry reads (fragile web server)."""
        info = {}
        for label, key in (
            ("system.gputemperature", "gpu_temp"),
            ("system.cputemperature", "cpu_temp"),
            ("system.fanspeed", "fan"),
            ("system.freememory", "free_memory"),
            ("system.buildversion", "build"),
        ) if with_system else ():
            text = " ".join(self.lines("GetSystemInfoByName", label))
            if key.endswith("_temp"):
                info[key] = parse_temp(text)
            elif key == "build":
                info[key] = text.strip() or None
            else:
                info[key] = parse_first_number(text)
        gui = parse_kv(self.lines("GetGUIStatus"))
        info["window"] = gui.get("ActiveWindowName")
        playing = parse_kv(self.lines("GetCurrentlyPlaying"))
        if playing.get("Filename") in (None, "[Nothing Playing]"):
            info["playing"] = None
        else:
            info["playing"] = playing
        vol = self.lines("GetVolume")
        info["volume"] = int(vol[0]) if vol and vol[0].isdigit() else None
        return info

    def screenshot(self, width: int = 640) -> bytes:
        import base64

        raw = self.cmd("TakeScreenshot", f"Z:\\ha_screenshot.jpg;false;0;{width};-1;80;true;true", timeout=20)
        data = re.sub(r"[^A-Za-z0-9+/=]", "", re.sub(r"<[^>]+>", "", raw))
        img = base64.b64decode(data + "=" * (-len(data) % 4))
        if not img.startswith(b"\xff\xd8"):
            raise XboxError("XBMC did not return a JPEG")
        return img

    def send_key(self, name_or_code: str | int) -> None:
        code = XBMC_KEYS.get(str(name_or_code).lower(), name_or_code)
        self.cmd("SendKey", str(int(code)))

    def builtin(self, action: str) -> str:
        return " ".join(self.lines("ExecBuiltIn", action))


# ---------------------------------------------------------------- XBMC telemetry without the HTTP API

# XBMC4Gamers ships without a web server; its FTP runs built-ins (SITE RunScript), so the
# telemetry comes from a Python 2 script left on disk. It lives in E:\TDATA (writable from UnleashX).
SCRIPT_DIR = "E:\\TDATA\\ha_original_xbox"
SCRIPT_PATH = SCRIPT_DIR + "\\ha_info.py"
SCRIPT_OUT = SCRIPT_DIR + "\\ha_info.txt"
SCRIPT_VERSION = "5"

XBMC_SCRIPT = (
    "# ha_original_xbox v" + SCRIPT_VERSION + " - telemetry for Home Assistant (XBMC Python 2)\r\n"
    "import sys, time, xbmc, xbmcgui\r\n"
    "nonce = len(sys.argv) > 1 and sys.argv[1] or ''\r\n"
    "full = len(sys.argv) > 2 and sys.argv[2] == 'full'\r\n"
    "busy = xbmc.getLocalizedString(503)\r\n"
    "def get(label, wait):\r\n"
    "    v = xbmc.getInfoLabel(label)\r\n"
    "    n = 0\r\n"
    "    while wait and v == busy and n < 30:\r\n"
    "        time.sleep(0.5); v = xbmc.getInfoLabel(label); n += 1\r\n"
    "    return v\r\n"
    "fast = ['system.cputemperature', 'system.gputemperature', 'system.fanspeed', 'system.hddtemperature',\r\n"
    "        'system.freememory', 'system.currentwindow', 'system.uptime', 'system.buildversion',\r\n"
    "        'player.title', 'player.time', 'player.duration', 'musicplayer.artist']\r\n"
    "console = ['system.xboxversion', 'system.bios', 'system.kernelversion', 'system.xboxproduceinfo',\r\n"
    "           'system.cpufrequency']\r\n"
    "out = open('" + SCRIPT_OUT.replace("\\", "\\\\") + "', 'w')\r\n"
    "out.write('nonce=%s\\n' % nonce)\r\n"
    "out.write('window.id=%d\\n' % xbmcgui.getCurrentWindowId())\r\n"
    "out.write('player.paused=%d\\n' % xbmc.getCondVisibility('Player.Paused'))\r\n"
    "p = xbmc.Player()\r\n"
    "out.write('player.playing=%d\\n' % p.isPlaying())\r\n"
    "try:\r\n"
    "    out.write('player.file=%s\\nplayer.time_s=%d\\nplayer.total_s=%d\\n' % (p.getPlayingFile(), p.getTime(), p.getTotalTime()))\r\n"
    "except:\r\n"
    "    pass\r\n"
    "for l in fast: out.write('%s=%s\\n' % (l, get(l, l == 'system.hddtemperature')))\r\n"
    "if full:\r\n"
    "    for l in console: out.write('%s=%s\\n' % (l, get(l, True)))\r\n"
    "out.close()\r\n"
)

SCRIPT_FIELDS = {
    "system.cputemperature": ("cpu_temp", parse_temp),
    "system.gputemperature": ("gpu_temp", parse_temp),
    "system.hddtemperature": ("hdd_temp", parse_temp),
    "system.fanspeed": ("fan", parse_first_number),
    "system.freememory": ("free_memory", parse_first_number),
    "system.currentwindow": ("window", str),
    "system.uptime": ("uptime", str),
    "system.buildversion": ("build", str),
    "system.xboxversion": ("xbox_version", str),
    "system.bios": ("bios", str),
    "system.kernelversion": ("kernel", str),
    "system.xboxproduceinfo": ("produced", str),
    "system.cpufrequency": ("cpu_frequency", str),
}


# XBMC window ids (xbmcgui.getCurrentWindowId)
XBMC_WINDOWS = {
    10000: "Home", 10001: "Programs", 10002: "Pictures", 10003: "Files", 10004: "Settings",
    10005: "Music", 10006: "Videos", 10007: "System info", 10024: "Videos (files)",
    10025: "Videos (library)", 10500: "Playlist", 10501: "Music (files)",
    10502: "Music (library)", 12005: "Fullscreen video", 12006: "Visualisation", 12007: "Screensaver",
}


def _hms(seconds: str | None) -> str:
    """'95' -> '01:35'; empty/invalid -> ''."""
    if not seconds or not seconds.strip().isdigit():
        return ""
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def parse_script_output(text: str) -> dict:
    """ha_info.py output -> {'nonce':..., field: value}; empty and 'busy' become None."""
    raw = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
    out: dict = {"nonce": raw.get("nonce", "")}
    wid = raw.get("window.id", "").strip()
    window = XBMC_WINDOWS.get(int(wid), f"Window {wid}") if wid.isdigit() else None
    for label, (key, conv) in SCRIPT_FIELDS.items():
        value = raw.get(label, "").strip()
        # "ocupado"/"desconhecido": busy/unknown labels of a Portuguese-language XBMC
        if not value or value.lower() in ("busy", "ocupado", "unknown", "desconhecido"):
            out[key] = None
            continue
        try:
            out[key] = conv(value)
        except ValueError:
            out[key] = None
    if not out.get("window"):
        out["window"] = window
    if raw.get("player.playing", "").strip() == "1" or raw.get("player.title", "").strip():
        file = raw.get("player.file", "").strip()
        out["playing"] = {
            "Title": raw.get("player.title", "").strip() or file.replace("\\", "/").rsplit("/", 1)[-1],
            "Filename": file,
            "Artist": raw.get("musicplayer.artist", "").strip(),
            "Time": _hms(raw.get("player.time_s")) or raw.get("player.time", "").strip(),
            "Duration": _hms(raw.get("player.total_s")) or raw.get("player.duration", "").strip(),
            "PlayStatus": "Paused" if raw.get("player.paused", "0").strip() == "1" else "Playing",
        }
    else:
        out["playing"] = None
    return out
