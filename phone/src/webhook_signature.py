"""Signing a request by the Standard Webhooks scheme (https://www.standardwebhooks.com), as the
call center app checks its phone line's requests.

The signature is an HMAC-SHA256 of `<id>.<timestamp>.<body>`; it covers neither the method nor the
path, so the app takes each id once and every request, a retry too, needs an id of its own.
"""

import base64
import hashlib
import hmac


def signature(key: bytes, message_id: str, seconds: int, body: str) -> str:
    content = f"{message_id}.{seconds}.{body}".encode()
    digest = hmac.new(key, content, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def signed_headers(key: bytes, body: str, *, message_id: str, seconds: int) -> dict[str, str]:
    return {
        "webhook-id": message_id,
        "webhook-timestamp": str(seconds),
        "webhook-signature": f"v1,{signature(key, message_id, seconds, body)}",
    }
