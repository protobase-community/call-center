from call.remote_tracks import RemoteTracks
from call.webrtc import keep_extension_ids


def test_a_track_is_heard_once_it_is_both_listed_and_received():
    heard, gone = [], []
    tracks = RemoteTracks(lambda m, sid, t: heard.append((m, sid, t)), gone.append)
    track = object()
    tracks.received("s1", track)  # type: ignore[arg-type]
    assert heard == []
    listed = [{"sid": "s1", "member": "alice", "kind": "audio", "muted": False}]
    tracks.listed(listed + [{"sid": "v1", "member": "alice", "kind": "video", "muted": False}])
    assert heard == [("alice", "s1", track)]
    tracks.listed(listed)
    assert len(heard) == 1
    tracks.listed([])
    assert gone == ["s1"]


def test_an_offer_keeps_the_header_extension_ids_already_negotiated():
    mid = "urn:ietf:params:rtp-hdrext:sdes:mid"
    level = "urn:ietf:params:rtp-hdrext:ssrc-audio-level"
    remote = f"a=extmap:4 {mid}\r\na=extmap:1 {level}\r\n"
    offer = f"a=extmap:1 {mid}\r\na=extmap:2 {level}\r\n"
    assert keep_extension_ids(offer, remote) == remote
