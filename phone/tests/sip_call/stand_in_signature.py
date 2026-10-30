"""The stand-in's check of a phone line request, made the way the app's verifyStandardWebhook and
functions/phone-line/signed-request.ts make theirs: the three webhook headers, a timestamp within
five minutes, one `v1` entry of the space-separated signatures that matches, and a webhook-id of at
most 200 characters not taken before. Standard library only, so it runs on the SIPp image.
"""

import base64
import binascii
import hashlib
import hmac
from collections.abc import Mapping

TOLERANCE = 300
# ids are kept as long as the app keeps them, longer than any timestamp could pass
KEPT = 600
LONGEST_ID = 200


class Refused(Exception):
    """A request the app answers with 401 and nothing changed; the slug names the problem."""

    def __init__(self, slug: str) -> None:
        super().__init__(slug)
        self.slug = slug


def secret_key(secret: str) -> bytes:
    return base64.b64decode(secret.removeprefix("whsec_"), validate=True)


def _decoded(text: str) -> bytes | None:
    try:
        return base64.b64decode(text, validate=True) or None
    except binascii.Error:
        return


class SignatureCheck:
    def __init__(self, key: bytes) -> None:
        self._key = key
        # webhook-id: the time it was taken
        self._taken: dict[str, float] = {}

    def check(self, headers: Mapping[str, str], body: str, now: float) -> None:
        message_id = headers.get("webhook-id")
        timestamp = headers.get("webhook-timestamp")
        signatures = headers.get("webhook-signature")
        if not message_id or not timestamp or not signatures:
            raise Refused("invalid-signature")
        if not timestamp.isdigit() or abs(now - int(timestamp)) > TOLERANCE:
            raise Refused("invalid-signature")

        content = f"{message_id}.{timestamp}.{body}".encode()
        expected = hmac.new(self._key, content, hashlib.sha256).digest()
        if not any(self._matches(entry, expected) for entry in signatures.split(" ")):
            raise Refused("invalid-signature")
        if len(message_id) > LONGEST_ID:
            raise Refused("invalid-signature")

        self._taken = {key: at for key, at in self._taken.items() if at > now - KEPT}
        if message_id in self._taken:
            raise Refused("replayed-message")
        self._taken[message_id] = now

    @staticmethod
    def _matches(entry: str, expected: bytes) -> bool:
        version, _, text = entry.partition(",")
        signature = _decoded(text)
        return (
            version == "v1" and signature is not None and hmac.compare_digest(signature, expected)
        )
