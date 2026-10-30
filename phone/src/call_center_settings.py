"""Where the call center app's phone line is and the secret its requests are signed with.

Both are read at startup and both are required, so a wrong one stops the agent before any call.
The line's requests carry the caller's customer number and PIN, so they go over https, or plain
http only to this machine, such as a local stand-in of the app.
"""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

URL_VARIABLE = "CALL_CENTER_URL"
SECRET_VARIABLE = "CALL_CENTER_SECRET"
SECRET_PREFIX = "whsec_"
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


@dataclass(frozen=True)
class CallCenterSettings:
    # the app's phone-line function, such as https://example.com/api/functions/phone-line
    url: str
    # the Standard Webhooks key: the bytes the secret's base64 holds
    key: bytes


def call_center_settings(environ: Mapping[str, str]) -> CallCenterSettings:
    return CallCenterSettings(url=_url(environ), key=_key(environ))


def _required(environ: Mapping[str, str], variable: str, what: str) -> str:
    value = environ.get(variable, "")
    if not value:
        raise ValueError(f"{variable} is not set; give {what}")
    return value


def _url(environ: Mapping[str, str]) -> str:
    text = _required(environ, URL_VARIABLE, "the URL of the app's phone-line function")
    try:
        parts = urlsplit(text)
        host = parts.hostname
    except ValueError as error:
        raise ValueError(f"{URL_VARIABLE} is not a URL") from error

    if parts.scheme not in ("https", "http") or not host:
        raise ValueError(f"{URL_VARIABLE} is not an http or https URL with a host")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError(f"{URL_VARIABLE} takes no query, fragment or credentials")
    if parts.scheme == "http" and host not in LOOPBACK_HOSTS:
        raise ValueError(f"{URL_VARIABLE} must be https unless it is on this machine")
    return text.rstrip("/")


def _key(environ: Mapping[str, str]) -> bytes:
    text = _required(environ, SECRET_VARIABLE, "the phone line's whsec_ signing secret")
    if not text.startswith(SECRET_PREFIX):
        raise ValueError(f"{SECRET_VARIABLE} does not start with {SECRET_PREFIX}")
    try:
        key = base64.b64decode(text.removeprefix(SECRET_PREFIX), validate=True)
    except binascii.Error as error:
        raise ValueError(f"{SECRET_VARIABLE} is not {SECRET_PREFIX} and base64") from error
    if not key:
        raise ValueError(f"{SECRET_VARIABLE} holds no key after {SECRET_PREFIX}")
    return key
