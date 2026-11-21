"""One phone call's bridge: the caller's SIP room and the Protobase call on its record, joined.

Into the Protobase call goes one microphone track: every audio track of the SIP room mixed, the
caller, the assistant and the hold music. Into the SIP room goes one track of the bridge's own:
every member of the Protobase call mixed. Neither side hears itself, since the bridge never
receives its own track in either. The bridge marks in its room attributes whether staff are in
the call, which the agent follows, and leaves the call when the caller hangs up.
"""

import asyncio
from collections.abc import Callable

from aiortc import MediaStreamTrack
from livekit import rtc

from audio_mix import AudioMix
from call.call_client import CallClient
from call_audio import feed_member
from keyed_tasks import KeyedTasks
from mix_track import MixTrack
from room_audio import feed_room_track, play_mix, room_source
from staff_attribute import staff_attributes, staff_in

TRACK_NAME = "protobase-call"

OpenCall = Callable[[str], CallClient]


class CallBridge:
    def __init__(self, room: rtc.Room, caller_identity: str) -> None:
        self._room = room
        self._caller_identity = caller_identity
        self._to_call = AudioMix()
        self._from_call = AudioMix()
        self._room_tracks = KeyedTasks()
        self._members = KeyedTasks()
        self._background = KeyedTasks()
        self._staff: bool | None = None
        self.hung_up = asyncio.Event()

    def open_call(self, url: str) -> OpenCall:
        """A client for the call at `url` that joins with a session cookie."""
        return lambda cookie: CallClient(
            url, {"Cookie": cookie}, self._on_member_audio, self._members.stop, self._on_members
        )

    def hear_room(self) -> None:
        """Feeds every audio track of the room, but the bridge's own, into the call's mix."""
        self._room.on("track_subscribed", self._on_subscribed)
        self._room.on("track_unsubscribed", self._on_unsubscribed)
        self._room.on("participant_disconnected", self._on_disconnected)
        for participant in self._room.remote_participants.values():
            for publication in participant.track_publications.values():
                if publication.track is not None:
                    self._on_subscribed(publication.track, publication, participant)
        if self._caller_identity not in self._room.remote_participants:
            self.hung_up.set()

    async def bridge(self, client: CallClient) -> None:
        """Both directions, until the caller hangs up or the call ends for the bridge."""
        source = room_source()
        track = rtc.LocalAudioTrack.create_audio_track(TRACK_NAME, source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await self._room.local_participant.publish_track(track, options)
        self._background.start("playout", play_mix(self._from_call, source))
        # the call's messages, the answer to the publish too, come in while it runs
        call = asyncio.create_task(client.run())
        publishing = asyncio.create_task(client.publish(MixTrack(self._to_call)))
        hung_up = asyncio.create_task(self.hung_up.wait())
        try:
            await asyncio.wait([call, publishing, hung_up], return_when=asyncio.FIRST_COMPLETED)
            if publishing.done():
                # raises when the call refused the bridge's audio
                await publishing
                await asyncio.wait([call, hung_up], return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (publishing, hung_up, call):
                task.cancel()
            await asyncio.wait([publishing, hung_up, call])
        if call.done() and not call.cancelled():
            # the call ended for the bridge: CallLeft says why
            await call

    async def close(self, client: CallClient | None) -> None:
        self._room.off("track_subscribed", self._on_subscribed)
        self._room.off("track_unsubscribed", self._on_unsubscribed)
        self._room.off("participant_disconnected", self._on_disconnected)
        try:
            if client is not None:
                await client.leave()
        finally:
            await self._room_tracks.close()
            await self._members.close()
            await self._background.close()

    def _on_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO or publication.sid in self._room_tracks:
            return
        work = feed_room_track(track, self._to_call, publication.sid)
        self._room_tracks.start(publication.sid, work)

    def _on_unsubscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        self._room_tracks.stop(publication.sid)

    def _on_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        if participant.identity == self._caller_identity:
            self.hung_up.set()

    def _on_member_audio(self, member: str, sid: str, track: MediaStreamTrack) -> None:
        self._members.start(sid, feed_member(track, self._from_call, sid))

    def _on_members(self, members: list[str]) -> None:
        present = staff_in(members)
        if present == self._staff:
            return
        self._staff = present
        attributes = staff_attributes(present)
        self._background.stop("staff")
        self._background.start("staff", self._room.local_participant.set_attributes(attributes))
