"""The media link to a media server (Protobase's LiveKit plugin), over one peer connection.

As @protobase/client/calls' `sfuLink` does: the agent always offers, one offer at a time; the
server's `answer` maps each receiving section's `mid` to the track it carries, and `sections` asks
for more receiving sections. aiortc gathers its candidates into the offer, so only the server's
candidates travel separately.
"""

import asyncio
from collections.abc import Awaitable, Callable

from aiortc import MediaStreamTrack, RTCSessionDescription

from call.remote_tracks import RemoteTracks
from call.webrtc import create_offer, ice_candidate, peer_connection

Send = Callable[[dict], Awaitable[None]]


class SfuLink:
    def __init__(self, ice_servers: list[dict], send: Send, remote: RemoteTracks) -> None:
        self._pc = peer_connection(ice_servers, bundle=True)
        self._send = send
        self._remote = remote
        self._mids: dict[str, str] = {}
        self._early: list[dict] = []
        self._offer_id = 0
        self._in_flight = False
        self._again = False
        self._settled = asyncio.Event()
        self._settled.set()
        self._publishing: asyncio.Future | None = None
        self._pc.on("track", lambda track: self._match_tracks())

    async def receive(self, message: dict) -> None:
        kind = message["type"]
        if kind == "answer":
            if message["id"] != self._offer_id:
                return
            self._mids.update(message["mids"])
            await self._pc.setRemoteDescription(RTCSessionDescription(message["sdp"], "answer"))
            for candidate in self._early:
                await self._pc.addIceCandidate(ice_candidate(candidate))
            self._early.clear()
            self._match_tracks()
            await self._answered()
        elif kind == "candidate":
            if self._pc.remoteDescription is None:
                self._early.append(message["candidate"])
            elif (candidate := ice_candidate(message["candidate"])) is not None:
                await self._pc.addIceCandidate(candidate)
        elif kind == "sections":
            for _ in range(message["audio"]):
                self._pc.addTransceiver("audio", direction="recvonly")
            for _ in range(message["video"]):
                self._pc.addTransceiver("video", direction="recvonly")
            await self._request_offer()
        elif kind == "tracks":
            self._remote.listed(message["tracks"])
        elif kind == "published" and self._publishing is not None:
            self._publishing.set_result(message["tracks"])
        elif kind == "publish-refused" and self._publishing is not None:
            self._publishing.set_exception(
                RuntimeError(f"The call refused the agent's audio: {message['reason']}")
            )
        elif kind == "unpublished":
            raise RuntimeError("The call stopped the agent's audio")

    async def publish(self, source: str, track: MediaStreamTrack) -> None:
        self._pc.addTransceiver(track, direction="sendonly")
        self._publishing = asyncio.get_running_loop().create_future()
        await self._send(
            {"type": "publish", "tracks": [{"cid": track.id, "kind": "audio", "source": source}]}
        )
        try:
            await self._publishing
        finally:
            self._publishing = None
        await self._request_offer()
        await self._settled.wait()

    async def close(self) -> None:
        await self._pc.close()

    def _match_tracks(self) -> None:
        for transceiver in self._pc.getTransceivers():
            sid = self._mids.get(transceiver.mid or "")
            track = transceiver.receiver.track
            if sid is not None and track is not None and track.kind == "audio":
                self._remote.received(sid, track)

    async def _request_offer(self) -> None:
        if self._in_flight:
            self._again = True
            return
        await self._offer()

    async def _offer(self) -> None:
        self._in_flight = True
        self._again = False
        self._settled.clear()
        await self._pc.setLocalDescription(await create_offer(self._pc))
        self._offer_id += 1
        await self._send(
            {"type": "offer", "sdp": self._pc.localDescription.sdp, "id": self._offer_id}
        )

    async def _answered(self) -> None:
        self._in_flight = False
        if self._again:
            await self._offer()
            return
        self._settled.set()
