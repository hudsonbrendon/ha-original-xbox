"""Constants for the Original Xbox integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "original_xbox"

CONF_DASHBOARD = "dashboard"
DEFAULT_USERNAME = "xbox"
DEFAULT_PASSWORD = "xbox"
DEFAULT_DASHBOARD = "C:\\evoxdash.xbe"
MS_DASHBOARD = "C:\\xboxdash.xbe"
CONFIG_PATH = "C:\\Config.xml"

SCAN_INTERVAL_SECONDS = 15
DRIVES_REFRESH_SECONDS = 120
CONFIG_REFRESH_SECONDS = 300
LIBRARY_REFRESH_SECONDS = 6 * 3600
XBMC_SYSTEM_SECONDS = 60
QUIET_AFTER_LAUNCH_SECONDS = 25  # XBMC freezes if polled while it is closing
SESSION_GIVE_UP_SECONDS = 8 * 3600  # game launched by HA with no reply for 8 h -> off

# activity
ACT_DASHBOARD = "dashboard"
ACT_XBMC = "xbmc"
ACT_AVALAUNCH = "avalaunch"
ACT_EVOX = "evox"
ACT_OTHER = "other_app"
ACT_GAME = "game"
ACT_OFF = "off"
ACT_HUNG = "frozen"
ACTIVITIES = [ACT_DASHBOARD, ACT_XBMC, ACT_AVALAUNCH, ACT_EVOX, ACT_OTHER, ACT_GAME, ACT_HUNG, ACT_OFF]

CAT_GAMES = "games"
CAT_APPS = "apps"

# folders scanned in addition to the UnleashX menu ones
DEFAULT_ROOTS = [
    (CAT_GAMES, "E:\\Games"),
    (CAT_GAMES, "F:\\Games"),
    (CAT_GAMES, "G:\\Games"),
    (CAT_GAMES, "E:\\HDDLoader"),
    (CAT_GAMES, "F:\\HDDLoader"),
    (CAT_APPS, "E:\\Apps"),
    (CAT_APPS, "F:\\Apps"),
    (CAT_APPS, "G:\\Apps"),
]
