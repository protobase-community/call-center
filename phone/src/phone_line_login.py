"""The phone line's session in the app: a password sign-in whose session cookie joins the calls.

The sign-in goes without a cookie and without an Origin header, as a client that is no browser:
Better Auth checks the origin only of requests that carry a cookie or name an origin. The cookie
stays in memory for every call's join until a join is refused, and neither it nor the password
goes into an error or a log line.

A socket opened with the session cookie gets a fresh token from the session at each recheck, so
the call does not drop when a token expires, as a bearer token's socket would; the session lasts
as long as the app's sign-in keeps it, and a sign-in renews it.
"""

import threading

import aiohttp

SIGN_IN_PATH = "/api/auth/sign-in/email"
# seconds a sign-in may take; a caller's bridge waits on it
TIMEOUT = 10.0
REFUSED = (401, 403)


class SignInRefused(Exception):
    """The app refused the phone line's email and password: no sign-in is tried again for it."""

    def __init__(self, status: int) -> None:
        super().__init__(f"The app refused the phone line's sign-in ({status})")
        self.status = status


class SignInFailed(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"The phone line's sign-in answered {status}")
        self.status = status


class PhoneLineLogin:
    def __init__(self, origin: str, email: str, password: str) -> None:
        self._url = origin + SIGN_IN_PATH
        self._email = email
        self._password = password
        self._cookie: str | None = None
        # each call's bridge runs on a thread of its own and may sign in
        self._lock = threading.Lock()

    @property
    def cookie(self) -> str | None:
        """The `Cookie` header of the last sign-in, None before the first."""
        with self._lock:
            return self._cookie

    async def sign_in(self) -> str:
        """Signs in anew and keeps the session cookie; returns it as a `Cookie` header."""
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        # no cookie jar: the request carries no cookie, and the session's is kept here only
        async with (
            aiohttp.ClientSession(timeout=timeout, cookie_jar=aiohttp.DummyCookieJar()) as http,
            http.post(self._url, json={"email": self._email, "password": self._password}) as answer,
        ):
            if answer.status in REFUSED:
                raise SignInRefused(answer.status)
            if not answer.ok:
                raise SignInFailed(answer.status)
            cookie = "; ".join(f"{name}={morsel.value}" for name, morsel in answer.cookies.items())
        if not cookie:
            raise SignInFailed(answer.status)
        with self._lock:
            self._cookie = cookie
        return cookie
