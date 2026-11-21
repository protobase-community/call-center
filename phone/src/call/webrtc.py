"""What the media link needs from aiortc: a peer connection with Protobase's ICE servers, browser
candidates, and offers that keep the header extension ids already negotiated."""

import re

from aiortc import (
    RTCConfiguration,
    RTCIceCandidate,
    RTCIceServer,
    RTCPeerConnection,
    RTCRtpHeaderExtensionParameters,
    RTCSessionDescription,
)
from aiortc.rtcconfiguration import RTCBundlePolicy
from aiortc.sdp import candidate_from_sdp


def peer_connection(ice_servers: list[dict], *, bundle: bool = False) -> RTCPeerConnection:
    servers = [
        RTCIceServer(urls=s["urls"], username=s.get("username"), credential=s.get("credential"))
        for s in ice_servers
    ]
    policy = RTCBundlePolicy.MAX_BUNDLE if bundle else RTCBundlePolicy.BALANCED
    return RTCPeerConnection(RTCConfiguration(iceServers=servers, bundlePolicy=policy))


def ice_candidate(candidate: dict) -> RTCIceCandidate | None:
    """A candidate as `RTCIceCandidate.toJSON()` writes it; None for the end of candidates."""
    line = candidate.get("candidate", "")
    if not line:
        return None
    parsed = candidate_from_sdp(line.removeprefix("candidate:"))
    parsed.sdpMid = candidate.get("sdpMid")
    parsed.sdpMLineIndex = candidate.get("sdpMLineIndex")
    return parsed


def _extension_ids(sdp: str) -> dict[str, int]:
    return {uri: int(n) for n, uri in re.findall(r"^a=extmap:(\d+)(?:/\w+)? (\S+)", sdp, re.M)}


def keep_extension_ids(offer: str, remote: str) -> str:
    """`offer` with the RTP header extension ids `remote` gives the same extensions."""
    ids = _extension_ids(remote)

    def renumber(match: re.Match) -> str:
        uri = match.group(2)
        return f"a=extmap:{ids.get(uri, match.group(1))} {uri}"

    return re.sub(r"^a=extmap:(\d+) (\S+)", renumber, offer, flags=re.M)


async def create_offer(pc: RTCPeerConnection) -> RTCSessionDescription:
    """An offer that keeps the RTP header extension ids the connection negotiated.

    aiortc numbers its header extensions afresh in every offer, in the SDP and in the transceivers
    it receives with, and a browser that offered first refuses an offer that renumbers them ("RTP
    extension ID reassignment not allowed"). So both get the ids of the remote description back.
    The transceivers' `_headerExtensions` is aiortc's own (1.15) state: there is no public way.
    """
    offer = await pc.createOffer()
    remote = pc.remoteDescription
    if remote is None:
        return offer
    ids = _extension_ids(remote.sdp)
    for transceiver in pc.getTransceivers():
        transceiver._headerExtensions = [
            RTCRtpHeaderExtensionParameters(id=ids.get(e.uri, e.id), uri=e.uri)
            for e in transceiver._headerExtensions
        ]
    return RTCSessionDescription(keep_extension_ids(offer.sdp, remote.sdp), "offer")
