"""Which remote audio the agent hears: a track Protobase lists for it (`tracks`) whose media the
peer connection receives. Each such track goes to `on_audio` once, until it is no longer both."""

from collections.abc import Callable

from aiortc import MediaStreamTrack


class RemoteTracks:
    def __init__(
        self,
        on_audio: Callable[[str, str, MediaStreamTrack], None],
        on_gone: Callable[[str], None],
    ) -> None:
        self._on_audio = on_audio
        self._on_gone = on_gone
        self._listed: dict[str, str] = {}
        self._received: dict[str, MediaStreamTrack] = {}
        self._heard: dict[str, MediaStreamTrack] = {}

    def listed(self, tracks: list[dict]) -> None:
        """Protobase's `tracks` message: every remote track the agent hears."""
        self._listed = {t["sid"]: t["member"] for t in tracks if t["kind"] == "audio"}
        self._update()

    def received(self, sid: str, track: MediaStreamTrack) -> None:
        self._received[sid] = track
        self._update()

    def lost(self, sid: str) -> None:
        self._received.pop(sid, None)
        self._update()

    def _update(self) -> None:
        for sid, track in list(self._heard.items()):
            if self._listed.get(sid) is None or self._received.get(sid) is not track:
                del self._heard[sid]
                self._on_gone(sid)
        for sid, member in self._listed.items():
            track = self._received.get(sid)
            if track is not None and sid not in self._heard:
                self._heard[sid] = track
                self._on_audio(member, sid, track)
