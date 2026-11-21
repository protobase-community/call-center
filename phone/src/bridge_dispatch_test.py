import aiohttp
import pytest
from livekit import api

from bridge_dispatch import dispatch_bridge


class _Dispatches:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def create_dispatch(self, request: object) -> None:
        raise self._error


class _Api:
    def __init__(self, error: Exception) -> None:
        self.agent_dispatch = _Dispatches(error)


@pytest.mark.parametrize(
    "error", [api.TwirpError("unavailable", "no server", status=503), aiohttp.ClientError()]
)
async def test_a_failed_dispatch_leaves_the_call_with_the_assistant(
    error: Exception, caplog: pytest.LogCaptureFixture
):
    await dispatch_bridge(_Api(error), "call-test", 7)  # type: ignore[arg-type]
    assert "no bridge for phone call 7" in caplog.text


async def test_another_failure_is_not_hidden():
    with pytest.raises(ValueError):
        await dispatch_bridge(_Api(ValueError("bug")), "call-test", 7)  # type: ignore[arg-type]
