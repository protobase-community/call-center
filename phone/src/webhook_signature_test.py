import base64

from webhook_signature import signed_headers


def test_signs_as_the_apps_own_signer_does():
    # made by the app's tests/phone-line-signer.ts with the same secret, id, time and body
    key = base64.b64decode("YSB0ZXN0IHNlY3JldCBvZiB0aGUgcGhvbmUgbGluZQ==")

    headers = signed_headers(key, '{"room_name":"call-1"}', message_id="msg_1", seconds=1700000000)

    assert headers == {
        "webhook-id": "msg_1",
        "webhook-timestamp": "1700000000",
        "webhook-signature": "v1,l526S7XxeFRcMsY1yu4geirmpvH3Ojy/bnBBJtytVjY=",
    }
