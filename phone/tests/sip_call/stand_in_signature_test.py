import base64

import pytest

from stand_in_signature import Refused, SignatureCheck

KEY = base64.b64decode("YSB0ZXN0IHNlY3JldCBvZiB0aGUgcGhvbmUgbGluZQ==")
BODY = '{"room_name":"call-1"}'
NOW = 1700000000
# made by the app's tests/phone-line-signer.ts
SIGNED = {
    "webhook-id": "msg_1",
    "webhook-timestamp": str(NOW),
    "webhook-signature": "v1,l526S7XxeFRcMsY1yu4geirmpvH3Ojy/bnBBJtytVjY=",
}


def test_takes_a_request_the_app_would_take_once():
    check = SignatureCheck(KEY)

    check.check(SIGNED, BODY, NOW + 299)
    with pytest.raises(Refused, match="replayed-message"):
        check.check(SIGNED, BODY, NOW + 299)


def test_takes_any_matching_v1_entry():
    signatures = f"v2,abc= v1,bm90IGl0 {SIGNED['webhook-signature']}"

    SignatureCheck(KEY).check({**SIGNED, "webhook-signature": signatures}, BODY, NOW)


@pytest.mark.parametrize(
    ("headers", "body", "now"),
    [
        ({**SIGNED, "webhook-signature": ""}, BODY, NOW),
        ({"webhook-id": "msg_1", "webhook-timestamp": str(NOW)}, BODY, NOW),
        (SIGNED, BODY + " ", NOW),
        (SIGNED, BODY, NOW + 301),
        (SIGNED, BODY, NOW - 301),
        ({**SIGNED, "webhook-id": "msg_2"}, BODY, NOW),
    ],
    ids=["empty", "missing", "body", "stale", "ahead", "other id"],
)
def test_refuses_what_the_app_refuses(headers: dict[str, str], body: str, now: int):
    with pytest.raises(Refused, match="invalid-signature"):
        SignatureCheck(KEY).check(headers, body, now)
