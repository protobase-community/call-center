"""For the tests: the app's password sign-in and its call socket, as the bridge meets them.

The sign-in takes one email and password and sets a new session cookie, refusing a request that
carries a cookie or an Origin header; the socket admits only a session not revoked, answers
`join` with `joined` in the mode given, then sends `members`.
"""

import json
import secrets
from dataclasses import dataclass, field

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

EMAIL = "phone-line@example.com"
PASSWORD = "the phone line's test password"
COOKIE_NAME = "better-auth.session_token"


@dataclass
class SignInStandIn:
    mode: str = "sfu"
    members: list[str] = field(default_factory=lambda: ["caller", "user-7"])
    sessions: set[str] = field(default_factory=set)
    sign_ins: int = 0
    joins: list[str | None] = field(default_factory=list)
    server: TestServer | None = None

    @property
    def origin(self) -> str:
        if self.server is None:
            raise RuntimeError("The stand-in has not started")
        return str(self.server.make_url("")).rstrip("/")

    def revoke(self) -> None:
        self.sessions.clear()

    async def start(self) -> None:
        app = web.Application()
        app.router.add_post("/api/auth/sign-in/email", self._sign_in)
        app.router.add_get("/api/functions/phone-call", self._socket)
        self.server = TestServer(app)
        await self.server.start_server()

    async def close(self) -> None:
        if self.server is not None:
            await self.server.close()

    async def _sign_in(self, request: web.Request) -> web.Response:
        self.sign_ins += 1
        if "Cookie" in request.headers or "Origin" in request.headers:
            return web.Response(status=403)
        body = await request.json()
        if body != {"email": EMAIL, "password": PASSWORD}:
            return web.Response(status=401)
        token = secrets.token_hex(8)
        self.sessions.add(token)
        response = web.json_response({"token": token})
        response.set_cookie(COOKIE_NAME, token, httponly=True)
        return response

    async def _socket(self, request: web.Request) -> web.StreamResponse:
        token = request.cookies.get(COOKIE_NAME)
        self.joins.append(token)
        if token not in self.sessions or "Origin" in request.headers:
            return web.Response(status=401)
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        async for message in socket:
            if message.type != WSMsgType.TEXT or json.loads(message.data)["type"] != "join":
                continue
            joined = {"type": "joined", "call": "c1", "mode": self.mode, "participant": "p1"}
            await socket.send_json({**joined, "iceServers": []})
            roster = [{"member": m, "joined_at": "2026-11-21T12:00:00Z"} for m in self.members]
            await socket.send_json({"type": "members", "members": roster})
        return socket
