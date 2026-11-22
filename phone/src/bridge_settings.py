"""What the bridge reads at startup: where the app is, and the phone line's account in it.

The app is the one CALL_CENTER_URL names, under the same rule as the agent's: https, or plain
http only to this machine, since the sign-in carries the password. PHONE_LINE_EMAIL and
PHONE_LINE_PASSWORD are an account of the app's `phone_line` role; startup stops without them.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from call_center_settings import call_center_url

EMAIL_VARIABLE = "PHONE_LINE_EMAIL"
PASSWORD_VARIABLE = "PHONE_LINE_PASSWORD"


@dataclass(frozen=True)
class BridgeSettings:
    # the app's origin, such as https://example.com
    origin: str
    email: str
    password: str = field(repr=False)


def bridge_settings(environ: Mapping[str, str]) -> BridgeSettings:
    parts = urlsplit(call_center_url(environ))
    return BridgeSettings(
        origin=f"{parts.scheme}://{parts.netloc}",
        email=_required(environ, EMAIL_VARIABLE, "the email of the app's phone_line account"),
        password=_required(environ, PASSWORD_VARIABLE, "the password of that account"),
    )


def _required(environ: Mapping[str, str], variable: str, what: str) -> str:
    value = environ.get(variable, "")
    if not value:
        raise ValueError(f"{variable} is not set; give {what}")
    return value
