#!/bin/sh
# Starts livekit-server on the key pair from .env, refusing a weak or malformed pair and dev mode.
# The server's API accepts requests from any web page, so only a secret no site knows guards it, and
# dev mode adds debug pages that need no token at all.
set -eu

dev_mode() {
  echo "livekit-server must not run with $1: dev mode serves room names and profiles to any web page" >&2
  exit 1
}
# the server turns dev mode on from --dev, from --development or LIVEKIT_DEVELOPMENT (a flag it makes
# for its config's development field), or from a config file or body, which compose never passes
for arg in "$@"; do
  case "$arg" in
    --dev | -dev | --dev=* | -dev=* | --development | -development | --development=* | -development=*)
      dev_mode "${arg%%=*}"
      ;;
    --config | -config | --config=* | -config=* | --config-body | -config-body | --config-body=* | -config-body=*)
      dev_mode "${arg%%=*} (a config could turn on dev mode)"
      ;;
  esac
done
if [ -n "${LIVEKIT_DEVELOPMENT+set}" ]; then dev_mode LIVEKIT_DEVELOPMENT; fi
if [ -n "${LIVEKIT_CONFIG+set}" ]; then dev_mode "LIVEKIT_CONFIG (a config could turn on dev mode)"; fi

case "$LIVEKIT_API_KEY" in
  *[!A-Za-z0-9_-]* | "")
    echo "LIVEKIT_API_KEY must be letters, digits, - or _" >&2
    exit 1
    ;;
esac

# letters and digits only, so the pair below always parses as YAML strings (a value that parsed as
# a number would be dropped, and the server would refuse to start without keys)
case "$LIVEKIT_API_SECRET" in
  *[!A-Za-z0-9]* | "")
    echo "LIVEKIT_API_SECRET must be at least 32 letters or digits: generate one with openssl rand -hex 32" >&2
    exit 1
    ;;
esac
if [ "${#LIVEKIT_API_SECRET}" -lt 32 ]; then
  echo "LIVEKIT_API_SECRET must be at least 32 letters or digits: generate one with openssl rand -hex 32" >&2
  exit 1
fi

export LIVEKIT_KEYS="\"$LIVEKIT_API_KEY\": \"$LIVEKIT_API_SECRET\""
unset LIVEKIT_API_KEY LIVEKIT_API_SECRET
exec /livekit-server "$@"
