"""A stand-in of the app's phone line for the tests that call it, from tests/sip_call."""

import base64
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from call_center import CallCenter
from call_center_settings import call_center_settings
from stand_in_server import FUNCTION_PATH, stand_in_server

SECRET = "whsec_" + base64.b64encode(b"the phone line's test secret").decode()


@dataclass
class StandIn:
    url: str
    secret: str
    log: Path

    def call_center(self) -> CallCenter:
        return CallCenter(
            call_center_settings({"CALL_CENTER_URL": self.url, "CALL_CENTER_SECRET": self.secret})
        )

    def requests(self) -> list[dict[str, Any]]:
        """What the stand-in answered, in order."""
        return [json.loads(line) for line in self.log.read_text().splitlines()]


@pytest.fixture
def stand_in(tmp_path: Path) -> Iterator[StandIn]:
    log = tmp_path / "phone-line.jsonl"
    log.touch()
    server = stand_in_server(0, str(log), base64.b64decode(SECRET.removeprefix("whsec_")))
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield StandIn(f"http://127.0.0.1:{server.server_port}{FUNCTION_PATH}", SECRET, log)
    server.shutdown()
    server.server_close()
