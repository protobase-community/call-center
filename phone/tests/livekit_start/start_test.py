"""livekit/start.sh refuses a weak or malformed key pair and dev mode before it starts the server.

The checks run before `exec /livekit-server`, so these run the script with no server installed:
a refused pair exits 1 with the message, an accepted one gets as far as the missing binary.
"""

import subprocess
from pathlib import Path

import pytest

START = Path(__file__).parent.parent.parent / "livekit" / "start.sh"
GOOD_SECRET = "0123456789abcdef" * 4


COMPOSE_ARGS = [
    "--bind",
    "0.0.0.0",
    "--node-ip",
    "127.0.0.1",
    "--udp-port",
    "7882",
    "--redis-host",
    "redis:6379",
]


def start(key: str, secret: str, *args: str, **extra_env: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "LIVEKIT_API_KEY": key,
        "LIVEKIT_API_SECRET": secret,
        **extra_env,
    }
    return subprocess.run(["sh", str(START), *args], env=env, capture_output=True, text=True)


@pytest.mark.parametrize(
    "secret",
    [
        "secret",
        "a" * 31,
        "",
        '"' + "a" * 63,
        "\\" + "a" * 63,
        "a" * 32 + " ",
        "a" * 32 + "\n",
    ],
)
def test_refuses_a_weak_or_malformed_secret(secret: str):
    result = start("local", secret)

    assert result.returncode == 1
    assert "openssl rand -hex 32" in result.stderr
    if secret:
        assert secret not in result.stderr


@pytest.mark.parametrize("key", ["", "a key", 'local"', "local:"])
def test_refuses_a_malformed_key(key: str):
    result = start(key, GOOD_SECRET)

    assert result.returncode == 1
    assert "LIVEKIT_API_KEY must be" in result.stderr


@pytest.mark.parametrize("secret", [GOOD_SECRET, "1234567890" * 4])
def test_accepts_a_long_alphanumeric_secret(secret: str):
    result = start("local", secret, *COMPOSE_ARGS)

    # past the checks: the exec of the server, which is not installed here, is what fails
    assert "must be" not in result.stderr
    assert "/livekit-server" in result.stderr


@pytest.mark.parametrize(
    "flag",
    [
        "--dev",
        "-dev",
        "--dev=true",
        "--dev=false",
        "--development",
        "-development",
        "--development=true",
        "--config",
        "--config=livekit.yaml",
        "--config-body=development: true",
        "-config-body",
    ],
)
@pytest.mark.parametrize("position", ["first", "after --bind", "only"])
def test_refuses_dev_mode(flag: str, position: str):
    args = {
        "first": [flag, *COMPOSE_ARGS],
        "after --bind": ["--bind", "0.0.0.0", flag],
        "only": [flag],
    }

    result = start("local", GOOD_SECRET, *args[position])

    assert result.returncode == 1
    assert f"must not run with {flag.split('=')[0]}" in result.stderr


@pytest.mark.parametrize(
    "variable,value",
    [
        ("LIVEKIT_DEVELOPMENT", "true"),
        ("LIVEKIT_DEVELOPMENT", ""),
        ("LIVEKIT_CONFIG", "development: true"),
    ],
)
def test_refuses_dev_mode_from_the_environment(variable: str, value: str):
    result = start("local", GOOD_SECRET, *COMPOSE_ARGS, **{variable: value})

    assert result.returncode == 1
    assert f"must not run with {variable}" in result.stderr


@pytest.mark.parametrize(
    "args", [["--redis-host", "dev-redis:6379"], ["--node-ip", "devbox"], ["--devices"]]
)
def test_accepts_arguments_that_only_contain_dev(args: list[str]):
    result = start("local", GOOD_SECRET, *args)

    assert "must not run with" not in result.stderr
    assert "/livekit-server" in result.stderr
