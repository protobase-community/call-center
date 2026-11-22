import pytest

from bridge_settings import bridge_settings

ENVIRON = {
    "CALL_CENTER_URL": "https://calls.example.com/api/functions/phone-line",
    "PHONE_LINE_EMAIL": "phone-line@example.com",
    "PHONE_LINE_PASSWORD": "a long password",
}


def test_the_app_is_the_origin_of_the_phone_line():
    settings = bridge_settings(ENVIRON)
    assert settings.origin == "https://calls.example.com"
    assert settings.email == "phone-line@example.com"


def test_the_password_stays_out_of_its_repr():
    assert "a long password" not in repr(bridge_settings(ENVIRON))


def test_plain_http_only_on_this_machine():
    local = {**ENVIRON, "CALL_CENTER_URL": "http://127.0.0.1:5173/api/functions/phone-line"}
    assert bridge_settings(local).origin == "http://127.0.0.1:5173"
    with pytest.raises(ValueError, match="must be https"):
        bridge_settings({**ENVIRON, "CALL_CENTER_URL": "http://calls.example.com/api"})


@pytest.mark.parametrize("variable", ["CALL_CENTER_URL", "PHONE_LINE_EMAIL", "PHONE_LINE_PASSWORD"])
def test_stops_without_a_setting(variable: str):
    environ = {k: v for k, v in ENVIRON.items() if k != variable}
    with pytest.raises(ValueError, match=f"{variable} is not set"):
        bridge_settings(environ)
