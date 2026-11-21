"""The bridge server reads its settings at import, so a missing one stops it before any call."""

import importlib
import sys

import dotenv
import pytest

from bridge_name import BRIDGE_NAME


def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # never the developer's .env
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_, **__: False)
    monkeypatch.setenv("CALL_CENTER_URL", "https://calls.example.com/api/functions/phone-line")
    monkeypatch.setenv("PHONE_LINE_EMAIL", "phone-line@example.com")
    monkeypatch.setenv("PHONE_LINE_PASSWORD", "a long password")
    monkeypatch.delitem(sys.modules, "bridge", raising=False)


@pytest.mark.parametrize("variable", ["PHONE_LINE_EMAIL", "PHONE_LINE_PASSWORD"])
def test_stops_without_the_phone_line_account(monkeypatch: pytest.MonkeyPatch, variable: str):
    _environment(monkeypatch)
    monkeypatch.delenv(variable)
    with pytest.raises(ValueError, match=f"{variable} is not set"):
        importlib.import_module("bridge")


def test_registers_as_the_bridge_on_the_app_of_the_phone_line(monkeypatch: pytest.MonkeyPatch):
    _environment(monkeypatch)
    bridge = importlib.import_module("bridge")
    assert bridge.socket_origin == "wss://calls.example.com"
    assert bridge.server._agent_name == BRIDGE_NAME
