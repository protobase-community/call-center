from staff_attribute import staff_attributes, staff_in, staff_present


def test_staff_are_in_when_anyone_but_the_caller_is():
    assert not staff_in([])
    assert not staff_in(["caller"])
    assert staff_in(["caller", "user-7"])


def test_the_attribute_round_trips():
    assert staff_present(staff_attributes(True)) is True
    assert staff_present(staff_attributes(False)) is False
    assert staff_present({"sip.phoneNumber": "+31205550101"}) is None
