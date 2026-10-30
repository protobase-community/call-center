import json

from check_pin_call import main, missing_steps


def _call(call_id: int) -> dict:
    return {"method": "POST", "path": "/calls", "status": 201, "answer": {"id": call_id}}


def _verify(call_id: int, result: str) -> dict:
    path = f"/calls/{call_id}/verify"
    return {"method": "POST", "path": path, "status": 200, "answer": {"result": result}}


def _ticket(call_id: int) -> dict:
    return {"method": "POST", "path": f"/calls/{call_id}/tickets", "status": 201, "answer": {}}


def _ended(call_id: int) -> dict:
    path = f"/calls/{call_id}/status"
    return {"method": "POST", "path": path, "status": 200, "answer": {"status": "ended"}}


def _customer(call_id: int) -> dict:
    return {"method": "GET", "path": f"/calls/{call_id}/customer", "status": 200, "answer": {}}


PIN_CALL = [_call(2), _verify(2, "not_verified"), _verify(2, "verified"), _ticket(2), _ended(2)]


def test_passes_the_steps_in_order_with_others_between():
    records = [_call(1), _ended(1), *PIN_CALL[:3], _customer(2), *PIN_CALL[3:]]

    assert missing_steps(records) == []


def test_reads_only_the_last_call():
    records = [*PIN_CALL[:4], _call(3), _ended(2)]

    assert missing_steps(records) == [
        "a wrong PIN refused",
        "the right PIN verified",
        "a ticket created",
        "the call ended",
    ]


def test_fails_steps_out_of_order():
    records = [_call(2), _verify(2, "verified"), _verify(2, "not_verified"), _ticket(2), _ended(2)]

    assert missing_steps(records) == [
        "the right PIN verified",
        "a ticket created",
        "the call ended",
    ]


def test_fails_a_call_without_a_ticket():
    assert missing_steps([*PIN_CALL[:3], PIN_CALL[4]]) == ["a ticket created", "the call ended"]


def test_main_prints_the_verdict(tmp_path, capsys):
    log = tmp_path / "phone-line.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in PIN_CALL[:4]))

    assert main(str(log), wait=0) == 1
    assert json.loads(capsys.readouterr().out)["missing"] == ["the call ended"]
