"""Joining a call with the phone line's session cookie, signing in again once when it is refused.

A join refused with 401, such as after an admin revoked the session, signs in anew and joins once
more; a second 401 gives up on the call. A refused sign-in, a wrong password for example, gives up
at once. Neither is tried again for the call.
"""

from collections.abc import Awaitable, Callable

from websockets.exceptions import InvalidStatus

from phone_line_login import PhoneLineLogin

UNAUTHORIZED = 401


class JoinRefused(Exception):
    def __init__(self) -> None:
        super().__init__("The app refused the phone line's join right after a new sign-in (401)")


def _unauthorized(error: InvalidStatus) -> bool:
    return error.response.status_code == UNAUTHORIZED


async def join_signed_in[T](login: PhoneLineLogin, join: Callable[[str], Awaitable[T]]) -> T:
    """`join(cookie)` with the kept session cookie, or a new one when there is none yet."""
    cookie = login.cookie or await login.sign_in()
    try:
        return await join(cookie)
    except InvalidStatus as error:
        if not _unauthorized(error):
            raise
    try:
        return await join(await login.sign_in())
    except InvalidStatus as error:
        if not _unauthorized(error):
            raise
        raise JoinRefused() from error
