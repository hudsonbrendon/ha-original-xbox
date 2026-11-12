"""Media player: console state, current game with cover, launching games and browsing the library."""

from __future__ import annotations

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XboxConfigEntry
from .api import XboxError, parse_duration
from .const import (
    ACT_DASHBOARD,
    ACT_HUNG,
    ACT_OFF,
    ACT_XBMC,
    CAT_APPS,
    CAT_GAMES,
    MS_DASHBOARD,
)
from .entity import XboxEntity

ROOT = "root"
CATEGORY_TITLES = {CAT_GAMES: "Games", CAT_APPS: "Apps"}


async def async_setup_entry(
    hass: HomeAssistant, entry: XboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([XboxMediaPlayer(entry.runtime_data, "console")])


class XboxMediaPlayer(XboxEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_media_content_type = MediaType.GAME
    _attr_media_image_remotely_accessible = False
    BASE = (
        MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    XBMC = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SEEK
    )

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        if self.data.get("xbmc") is not None:
            return self.BASE | self.XBMC
        if self._xbmc is not None:  # XBMC without HTTP: controls via FTP, no seek and no volume readback
            return self.BASE | (self.XBMC & ~MediaPlayerEntityFeature.SEEK)
        return self.BASE

    @property
    def _xbmc(self) -> dict | None:
        if self.data.get("activity") != ACT_XBMC:
            return None
        return self.data.get("xbmc") or self.data.get("telemetry") or ({} if self.data.get("online") else None)

    @property
    def _playing(self) -> dict:
        return (self._xbmc or {}).get("playing") or {}

    @property
    def state(self) -> MediaPlayerState:
        activity = self.data.get("activity")
        if activity in (None, ACT_OFF):
            return MediaPlayerState.OFF
        if activity == ACT_DASHBOARD:
            return MediaPlayerState.IDLE
        if activity == ACT_HUNG:
            return MediaPlayerState.ON
        if self._xbmc is not None:
            status = self._playing.get("PlayStatus", "").lower()
            if not self._playing:
                return MediaPlayerState.ON
            return MediaPlayerState.PAUSED if status == "paused" else MediaPlayerState.PLAYING
        return MediaPlayerState.PLAYING

    @property
    def _current(self) -> dict | None:
        return self.data.get("current") if not self.in_dashboard else None

    @property
    def media_title(self) -> str | None:
        if self.data.get("activity") == ACT_HUNG:
            return "Frozen (restart it with the power button)"
        p = self._playing
        if p:
            return p.get("Title") or p.get("Filename", "").replace("\\", "/").rsplit("/", 1)[-1]
        cur = self._current
        if cur:
            return cur["name"]
        if self.data.get("activity") == ACT_HUNG:
            return "Frozen (restart it with the power button)"
        if self.state == MediaPlayerState.PLAYING:
            return "Game or app"
        return "Dashboard" if self.in_dashboard else None

    @property
    def media_artist(self) -> str | None:
        return self._playing.get("Artist") or None

    @property
    def media_album_name(self) -> str | None:
        return self._playing.get("Album") or None

    @property
    def media_duration(self) -> int | None:
        return parse_duration(self._playing.get("Duration"))

    @property
    def media_position(self) -> int | None:
        return parse_duration(self._playing.get("Time"))

    @property
    def media_position_updated_at(self):
        return self.data.get("at") if self._playing else None

    @property
    def volume_level(self) -> float | None:
        vol = (self._xbmc or {}).get("volume")
        return vol / 100 if vol is not None else None

    @property
    def media_content_id(self) -> str | None:
        cur = self._current
        return cur.get("path") if cur else None

    @property
    def media_image_hash(self) -> str | None:
        cur = self._current
        return cur.get("title_id") if cur else None

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        cur = self._current
        if not cur or not cur.get("title_id"):
            return None, None
        png = await self.coordinator.async_cover(cur["title_id"], cur.get("path"))
        return (png, "image/png") if png else (None, None)

    @property
    def source(self) -> str | None:
        cur = self._current
        return cur["name"] if cur else None

    @property
    def source_list(self) -> list[str]:
        return sorted({i["name"] for i in self.coordinator.library}, key=str.casefold)

    @property
    def extra_state_attributes(self) -> dict:
        cur = self._current or {}
        return {
            "activity": self.data.get("activity"),
            "path": cur.get("path"),
            "title_id": cur.get("title_id"),
            "launched_by_ha": cur.get("by_ha"),
        }

    async def async_select_source(self, source: str) -> None:
        item = self.coordinator.find_item(source)
        if item is None:
            raise HomeAssistantError(f"not in the library: {source}")
        await self._run(self.coordinator.async_launch(item["path"]))

    async def async_play_media(self, media_type: str, media_id: str, **kwargs) -> None:
        await self._run(self.coordinator.async_launch(media_id))

    async def async_media_play(self) -> None:
        if self._playing.get("PlayStatus", "").lower() == "paused":
            await self._run(self.coordinator.async_media("pause"))

    async def async_media_pause(self) -> None:
        if self._playing.get("PlayStatus", "").lower() != "paused":
            await self._run(self.coordinator.async_media("pause"))

    async def async_media_stop(self) -> None:
        await self._run(self.coordinator.async_media("stop"))

    async def async_media_next_track(self) -> None:
        await self._run(self.coordinator.async_media("next"))

    async def async_media_previous_track(self) -> None:
        await self._run(self.coordinator.async_media("previous"))

    async def async_set_volume_level(self, volume: float) -> None:
        await self._run(self.coordinator.async_media("volume", round(volume * 100)))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.coordinator.async_media("mute"))

    async def async_media_seek(self, position: float) -> None:
        duration = self.media_duration
        if duration:
            await self._run(self.coordinator.async_media("seek", round(100 * position / duration)))

    async def async_turn_off(self) -> None:  # works from UnleashX and XBMC
        await self._run(self.coordinator.async_power("SHUTDOWN"))

    async def _run(self, coro) -> None:
        try:
            await coro
        except XboxError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------------ browsing

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        if media_content_id in CATEGORY_TITLES:
            items = sorted(
                (i for i in self.coordinator.library if i["category"] == media_content_id),
                key=lambda i: i["name"].casefold(),
            )
            children = [
                BrowseMedia(
                    title=i["name"],
                    media_class=MediaClass.GAME if media_content_id == CAT_GAMES else MediaClass.APP,
                    media_content_type=MediaType.GAME if media_content_id == CAT_GAMES else MediaType.APP,
                    media_content_id=i["path"],
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(MediaType.GAME, i["path"], i.get("title_id"))
                    if i.get("title_id")
                    else None,
                )
                for i in items
            ]
            return BrowseMedia(
                title=CATEGORY_TITLES[media_content_id],
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                media_content_id=media_content_id,
                can_play=False,
                can_expand=True,
                children=children,
                children_media_class=MediaClass.GAME if media_content_id == CAT_GAMES else MediaClass.APP,
            )
        children = [
            BrowseMedia(
                title=title,
                media_class=MediaClass.DIRECTORY,
                media_content_type="",
                media_content_id=key,
                can_play=False,
                can_expand=True,
            )
            for key, title in CATEGORY_TITLES.items()
        ]
        children.append(
            BrowseMedia(
                title="Microsoft Dashboard",
                media_class=MediaClass.APP,
                media_content_type=MediaType.APP,
                media_content_id=MS_DASHBOARD,
                can_play=True,
                can_expand=False,
            )
        )
        return BrowseMedia(
            title="Xbox",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            media_content_id=ROOT,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_get_browse_image(
        self, media_content_type: str, media_content_id: str, media_image_id: str | None = None
    ) -> tuple[bytes | None, str | None]:
        png = await self.coordinator.async_cover(media_image_id, media_content_id)
        return (png, "image/png") if png else (None, None)
