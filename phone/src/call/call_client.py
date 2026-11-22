"""Joins a Protobase call as a member, over the socket of the app's function that admits members,
as `joinCall` from @protobase/client/calls does in a browser.

The protocol is JSON over that socket (see Protobase's `call-protocol.ts`): `join`, then `joined`
says whether media goes through a media server (`sfu`) or straight to each member (`peer`). Only
the media server path is supported: `peer` stops the client with PeerModeUnsupported. The media
link takes every message after `joined`. The client publishes one microphone track, hears the
audio tracks Protobase lists for it, and hands on who is in the call from each `members` message.

A lost socket is not resumed: the call client ends, and with it the bridge for that call.
"""

import asyncio
import json
from collections.abc import Callable

import websockets
from aiortc import MediaStreamTrack

from call.remote_tracks import RemoteTracks
from call.sfu_link import SfuLink


class CallLeft(Exception):
    """The call ended for the member: `reason` is Protobase's, such as `ended` or `removed`."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Left the call: {reason}")
        self.reason = reason


class PeerModeUnsupported(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The call sends media straight between members (peer), but the bridge supports only"
            " the LiveKit media server path (sfu): give the app a LiveKit calls backend"
        )


class JoinTimedOut(Exception):
    def __init__(self) -> None:
        super().__init__(f"The call did not take the member in within {JOIN_TIMEOUT:.0f} s")


# seconds from the open socket to `joined`; the caller is on the line meanwhile
JOIN_TIMEOUT = 15.0


class CallClient:
    def __init__(
        self,
        url: str,
        headers: dict[str, str],
        on_audio: Callable[[str, str, MediaStreamTrack], None],
        on_gone: Callable[[str], None],
        on_members: Callable[[list[str]], None],
    ) -> None:
        """`on_audio(member, sid, track)` for each remote audio track the member hears,
        `on_gone(sid)` when it no longer does, and `on_members(members)` with everyone in the
        call, this member too, whenever that changes."""
        self._url = url
        self._headers = headers
        self._remote = RemoteTracks(on_audio, on_gone)
        self._on_members = on_members
        self._socket: websockets.ClientConnection | None = None
        self._link: SfuLink | None = None
        self.participant: str | None = None

    async def join(self) -> None:
        """Opens the socket and returns once the member is in the call.

        A refused upgrade raises websockets' InvalidStatus, with the app's status, such as 401.
        """
        self._socket = await websockets.connect(self._url, additional_headers=self._headers)
        try:
            await self._send({"type": "join"})
            async with asyncio.timeout(JOIN_TIMEOUT):
                while self._link is None:
                    await self._handle(json.loads(await self._socket.recv()))
        except TimeoutError as error:
            await self._socket.close()
            raise JoinTimedOut() from error
        except BaseException:
            # a join that failed leaves no socket open
            await self._socket.close()
            raise

    async def publish(self, track: MediaStreamTrack) -> None:
        if self._link is None:
            raise RuntimeError("Publishing needs the call joined first")
        await self._link.publish("microphone", track)

    async def run(self) -> None:
        """Takes the server's messages until the call ends for the member; raises `CallLeft`."""
        if self._socket is None:
            raise RuntimeError("Running needs the call joined first")
        try:
            async for message in self._socket:
                await self._handle(json.loads(message))
        except websockets.ConnectionClosed:
            pass
        code = self._socket.close_code
        raise CallLeft({1000: "ended", 1008: "removed"}.get(code or 0, f"socket closed ({code})"))

    async def leave(self) -> None:
        """Says so when the socket is still open, then closes the socket and the media."""
        try:
            if self._socket is not None and self._socket.close_code is None:
                try:
                    await self._send({"type": "leave"})
                except websockets.ConnectionClosed:
                    # the server closed it meanwhile: the member is out of the call either way
                    pass
        finally:
            try:
                if self._socket is not None:
                    await self._socket.close()
            finally:
                if self._link is not None:
                    await self._link.close()

    async def _send(self, message: dict) -> None:
        if self._socket is None:
            raise RuntimeError("Sending needs the socket open")
        await self._socket.send(json.dumps(message))

    async def _handle(self, message: dict) -> None:
        kind = message["type"]
        if kind == "joined":
            if self._link is not None:
                raise RuntimeError("Protobase asked to join again, which the bridge cannot do")
            if message["mode"] != "sfu":
                raise PeerModeUnsupported()
            self.participant = message["participant"]
            self._link = SfuLink(message["iceServers"], self._send, self._remote)
        elif kind == "left":
            raise CallLeft(message["reason"])
        elif kind == "members":
            self._on_members([m["member"] for m in message["members"]])
        elif kind == "speakers":
            return
        elif self._link is None:
            raise RuntimeError(f"Protobase sent {kind} before the member joined")
        else:
            await self._link.receive(message)
