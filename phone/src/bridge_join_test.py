import asyncio
from collections.abc import AsyncIterator

import pytest

from bridge_join import JoinRefused, join_signed_in
from call.call_client import CallClient, PeerModeUnsupported
from phone_line_login import PhoneLineLogin, SignInRefused
from sign_in_stand_in import EMAIL, PASSWORD, SignInStandIn


@pytest.fixture
async def app() -> AsyncIterator[SignInStandIn]:
    stand_in = SignInStandIn()
    await stand_in.start()
    yield stand_in
    await stand_in.close()


def _login(app: SignInStandIn, password: str = PASSWORD) -> PhoneLineLogin:
    return PhoneLineLogin(app.origin, EMAIL, password)


def _join(app: SignInStandIn, members: list[list[str]]):
    url = app.origin.replace("http", "ws", 1) + "/api/functions/phone-call?phone_call=1"

    async def join(cookie: str) -> CallClient:
        client = CallClient(
            url, {"Cookie": cookie}, lambda *_: None, lambda _: None, members.append
        )
        await client.join()
        return client

    return join


async def test_joins_with_the_cookie_of_a_password_sign_in(app: SignInStandIn):
    login = _login(app)
    client = await join_signed_in(login, _join(app, []))
    await client.leave()
    assert app.sign_ins == 1
    assert app.joins == list(app.sessions)
    assert login.cookie == f"better-auth.session_token={app.joins[0]}"


async def test_later_joins_reuse_the_session(app: SignInStandIn):
    login = _login(app)
    for _ in range(2):
        await (await join_signed_in(login, _join(app, []))).leave()
    assert app.sign_ins == 1
    assert len(app.joins) == 2


async def test_a_revoked_session_signs_in_again_once(app: SignInStandIn):
    login = _login(app)
    await (await join_signed_in(login, _join(app, []))).leave()
    app.revoke()
    await (await join_signed_in(login, _join(app, []))).leave()
    assert app.sign_ins == 2
    assert app.joins[1] not in app.sessions
    assert app.joins[2] in app.sessions


async def test_a_second_refusal_gives_up(app: SignInStandIn, monkeypatch: pytest.MonkeyPatch):
    login = _login(app)
    # every new session is revoked at once
    monkeypatch.setattr(app, "sessions", set())
    sign_in = login.sign_in

    async def revoked_sign_in() -> str:
        cookie = await sign_in()
        app.revoke()
        return cookie

    monkeypatch.setattr(login, "sign_in", revoked_sign_in)
    with pytest.raises(JoinRefused):
        await join_signed_in(login, _join(app, []))
    assert app.sign_ins == 2
    assert len(app.joins) == 2


async def test_a_wrong_password_stops_without_a_retry(app: SignInStandIn):
    with pytest.raises(SignInRefused) as refused:
        await join_signed_in(_login(app, "wrong"), _join(app, []))
    assert app.sign_ins == 1
    assert app.joins == []
    assert "wrong" not in str(refused.value)


async def test_hands_on_who_is_in_the_call(app: SignInStandIn):
    members: list[list[str]] = []
    client = await join_signed_in(_login(app), _join(app, members))
    running = asyncio.create_task(client.run())
    while not members:
        await asyncio.sleep(0.01)
    running.cancel()
    await client.leave()
    assert members == [["caller", "user-7"]]


async def test_peer_mode_stops_with_a_clear_error(app: SignInStandIn):
    app.mode = "peer"
    with pytest.raises(PeerModeUnsupported, match="supports only the LiveKit"):
        await join_signed_in(_login(app), _join(app, []))
