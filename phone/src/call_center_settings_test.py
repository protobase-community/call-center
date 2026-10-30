import pytest

from call_center_settings import call_center_settings

SECRET = "whsec_YSB0ZXN0IHNlY3JldCBvZiB0aGUgcGhvbmUgbGluZQ=="
URL = "https://calls.example.com/api/functions/phone-line"


def test_reads_the_url_and_the_secrets_key():
    settings = call_center_settings({"CALL_CENTER_URL": URL + "/", "CALL_CENTER_SECRET": SECRET})

    assert settings.url == URL
    assert settings.key == b"a test secret of the phone line"


@pytest.mark.parametrize("url", ["http://localhost:8090", "http://127.0.0.1:8090/phone-line"])
def test_takes_plain_http_on_this_machine(url: str):
    settings = call_center_settings({"CALL_CENTER_URL": url, "CALL_CENTER_SECRET": SECRET})

    assert settings.url == url


@pytest.mark.parametrize(
    ("environ", "error"),
    [
        ({"CALL_CENTER_SECRET": SECRET}, "CALL_CENTER_URL is not set"),
        ({"CALL_CENTER_URL": "", "CALL_CENTER_SECRET": SECRET}, "CALL_CENTER_URL is not set"),
        ({"CALL_CENTER_URL": URL}, "CALL_CENTER_SECRET is not set"),
        ({}, "CALL_CENTER_URL is not set"),
    ],
)
def test_stops_without_a_setting(environ: dict[str, str], error: str):
    with pytest.raises(ValueError, match=error):
        call_center_settings(environ)


@pytest.mark.parametrize(
    "url",
    [
        "calls.example.com/phone-line",
        "ftp://calls.example.com",
        "https://",
        "https://calls.example.com/phone-line?x=1",
        "https://user:pass@calls.example.com",
        "http://calls.example.com/phone-line",
        "https://[not-an-address/",
    ],
)
def test_stops_on_a_malformed_url(url: str):
    with pytest.raises(ValueError, match="^CALL_CENTER_URL "):
        call_center_settings({"CALL_CENTER_URL": url, "CALL_CENTER_SECRET": SECRET})


@pytest.mark.parametrize("secret", ["YSB0ZXN0", "whsec_not base64!", "whsec_YQ"])
def test_stops_on_a_malformed_secret_without_showing_it(secret: str):
    with pytest.raises(ValueError, match="^CALL_CENTER_SECRET ") as raised:
        call_center_settings({"CALL_CENTER_URL": URL, "CALL_CENTER_SECRET": secret})

    assert secret.removeprefix("whsec_") not in str(raised.value)


def test_stops_on_a_secret_without_a_key():
    with pytest.raises(ValueError, match="CALL_CENTER_SECRET holds no key"):
        call_center_settings({"CALL_CENTER_URL": URL, "CALL_CENTER_SECRET": "whsec_"})
