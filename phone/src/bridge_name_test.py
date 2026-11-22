import pytest

from bridge_name import bridge_metadata, bridged_call


def test_the_call_id_round_trips():
    assert bridged_call(bridge_metadata(42)) == 42


def test_metadata_without_a_call_id_is_refused():
    with pytest.raises(ValueError):
        bridged_call('{"call_id": "42"}')
