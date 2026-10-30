import json

import pytest

from call_center import CallCenterError
from caller_info import CallerInfo
from conftest import StandIn
from phone_line_stand_in import CUSTOMER_NUMBER, PIN
from pin_entry import PinEntry, route_keys

WRONG_PIN = "111111"


async def _entry(stand_in: StandIn) -> tuple[PinEntry, CallerInfo, list[str]]:
    call_center = stand_in.call_center()
    caller = CallerInfo(call_id=await call_center.register_call("call-1", None))
    reports: list[str] = []
    return PinEntry(call_center, caller, reports.append), caller, reports


async def test_sends_the_two_sequences_to_the_check_and_nothing_to_the_model(stand_in: StandIn):
    pin_entry, caller, reports = await _entry(stand_in)
    model: list[str] = []
    deliver = route_keys(pin_entry, model.append)

    deliver("5")
    pin_entry.start()
    deliver(CUSTOMER_NUMBER)
    deliver(WRONG_PIN)
    await pin_entry.wait()
    assert not caller.verified
    pin_entry.start()
    deliver(CUSTOMER_NUMBER)
    deliver(PIN)
    await pin_entry.wait()
    deliver("7")

    assert [json.loads(report) for report in reports] == [{"verified": False}, {"verified": True}]
    assert caller.verified
    assert [json.loads(message) for message in model] == [{"keypad": "5"}, {"keypad": "7"}]
    verifications = [r["answer"] for r in stand_in.requests() if r["path"].endswith("/verify")]
    assert verifications == [{"result": "not_verified", "tries_left": 2}, {"result": "verified"}]


async def test_reports_a_locked_call(stand_in: StandIn):
    pin_entry, _, reports = await _entry(stand_in)

    for _ in range(3):
        pin_entry.start()
        pin_entry.take(CUSTOMER_NUMBER)
        pin_entry.take(WRONG_PIN)
        await pin_entry.wait()

    assert [json.loads(report)["verified"] for report in reports] == [False, False, "locked"]


async def test_a_pound_key_on_its_own_is_an_empty_entry(stand_in: StandIn):
    pin_entry, _, reports = await _entry(stand_in)

    pin_entry.start()
    pin_entry.take("#")
    pin_entry.take(PIN)
    await pin_entry.wait()

    assert json.loads(reports[0]) == {"verified": False}


async def test_a_restart_drops_the_entry_taken_so_far(stand_in: StandIn):
    pin_entry, caller, _ = await _entry(stand_in)

    pin_entry.start()
    pin_entry.take("99")
    pin_entry.start()
    pin_entry.take(CUSTOMER_NUMBER)
    pin_entry.take(PIN)
    await pin_entry.wait()

    assert caller.verified
    assert not pin_entry.active


async def test_tells_the_model_when_the_check_fails(stand_in: StandIn):
    pin_entry, caller, reports = await _entry(stand_in)
    assert caller.call_id is not None
    await stand_in.call_center().end_call(caller.call_id)

    pin_entry.start()
    pin_entry.take(CUSTOMER_NUMBER)
    pin_entry.take(PIN)
    with pytest.raises(CallCenterError):
        await pin_entry.wait()

    assert [json.loads(report) for report in reports] == [{"pin_check": "failed"}]
