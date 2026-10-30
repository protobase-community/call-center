import pytest

from call_center import CallCenter, CallCenterError
from call_center_settings import call_center_settings
from conftest import StandIn
from phone_line_stand_in import CUSTOMER_NUMBER, PIN


async def test_registers_a_call_once_per_room(stand_in: StandIn):
    call_center = stand_in.call_center()

    first = await call_center.register_call("call-1", "+31205550101")
    again = await call_center.register_call("call-1", "+31205550101")
    other = await call_center.register_call("call-2", None)

    assert first == again != other
    assert [r["status"] for r in stand_in.requests()] == [201, 200, 201]


async def test_verifies_a_caller_and_acts_for_them(stand_in: StandIn):
    call_center = stand_in.call_center()
    call = await call_center.register_call("call-1", None)

    assert await call_center.verify(call, CUSTOMER_NUMBER, "000000") == "not_verified"
    assert await call_center.verify(call, CUSTOMER_NUMBER, PIN) == "verified"
    customer = await call_center.customer(call)
    ticket = await call_center.create_ticket(call, "No dial tone", "Since this morning.")

    assert customer["name"] == "Ama Mensah"
    assert [t["subject"] for t in customer["tickets"]] == ["Invoice question"]
    assert ticket["subject"] == "No dial tone"
    assert ticket["status"] == "open"


async def test_a_refusal_names_the_route_status_and_problem_but_not_the_body(stand_in: StandIn):
    call_center = stand_in.call_center()
    call = await call_center.register_call("call-1", None)
    await call_center.end_call(call)

    with pytest.raises(CallCenterError) as refused:
        await call_center.verify(call, CUSTOMER_NUMBER, PIN)

    assert refused.value.status == 409
    assert refused.value.problem == "call-ended"
    assert str(refused.value) == f"POST /calls/{call}/verify answered 409 call-ended"


async def test_the_customer_is_out_of_reach_before_verification(stand_in: StandIn):
    call_center = stand_in.call_center()
    call = await call_center.register_call("call-1", None)

    with pytest.raises(CallCenterError) as refused:
        await call_center.customer(call)

    assert refused.value.status == 404


async def test_signs_each_request_with_an_id_of_its_own(stand_in: StandIn):
    settings = call_center_settings(
        {"CALL_CENTER_URL": stand_in.url, "CALL_CENTER_SECRET": stand_in.secret}
    )
    same_id = CallCenter(settings, new_message_id=lambda: "msg_same")

    await same_id.register_call("call-1", None)
    with pytest.raises(CallCenterError) as replayed:
        await same_id.register_call("call-2", None)

    assert replayed.value.problem == "replayed-message"


async def test_the_app_refuses_another_secret(stand_in: StandIn):
    other = CallCenter(
        call_center_settings(
            {"CALL_CENTER_URL": stand_in.url, "CALL_CENTER_SECRET": "whsec_b3RoZXI="}
        )
    )

    with pytest.raises(CallCenterError) as refused:
        await other.register_call("call-1", None)

    assert refused.value.status == 401
    assert stand_in.requests()[0]["status"] == 401
