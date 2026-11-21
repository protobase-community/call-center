#!/usr/bin/env bash
# Calls through the app as it runs: SIPp callers on the phone side, a staff member in Chromium on
# the app's side, and the bridge between them, on one LiveKit server.
#   1. hold: the caller asks for a person and waits with hold music; staff join and each side says
#      a line. 2. An admin revokes the phone line's sessions. 3. staff-first: staff join while the
#      assistant has the caller, say their line, hear the caller's, and leave; the assistant comes
#      back. 4. wrong-password: the bridge's sign-in is refused once and it gives up on the call.
# usage: phone/tests/bridge_call/run.sh   (from a checkout with `bun install` run and the app's
#   database migrated, as the README's local steps say; the model's key in phone/.env or the
#   environment; Chromium for Playwright: `bunx playwright install chromium`)
# It starts the app with `bun run dev` on port 5173 and the phone stack, with accounts and secrets
# of its own, and leaves the stack running. Stop your own `bun run dev` first. Writes everything to
# BRIDGE_CALL_OUT, by default a new private directory under /tmp: outside the project, since
# `bun run dev` closes every call's socket when a file in the project changes.
set -euo pipefail
phone=$(cd "$(dirname "$0")/../.." && pwd -P)
root=$(dirname "$phone")
out=${BRIDGE_CALL_OUT:-$(mktemp -d /tmp/call-center-bridge-call.XXXXXX)}
echo "writing to $out"
export SIP_CALL_OUT=$out
cd "$phone"
mkdir -p "$out"
rm -f "$out"/hold* "$out"/staff-first* "$out"/wrong-password* "$out/sessions.txt"
# a setting from the environment, else from phone/.env, as compose takes it
setting() {
  if [ -z "${!1:-}" ] && [ -f .env ]; then
    export "$1=$(grep -E "^$1=" .env | tail -1 | cut -d= -f2-)"
  fi
  [ -n "${!1:-}" ] || { echo "set $1 in phone/.env" >&2; exit 1; }
}
setting OPENAI_API_KEY
setting LIVEKIT_API_KEY
setting LIVEKIT_API_SECRET

# this run's accounts and phone line secret, whatever the app's .env names
run_id=$(openssl rand -hex 4)
password() { openssl rand -hex 16; }
export ADMIN_EMAIL="admin-$run_id@example.com" ADMIN_PASSWORD=$(password)
export STAFF_EMAIL="agent-$run_id@example.com" STAFF_PASSWORD=$(password)
export PHONE_LINE_EMAIL="phone-line-$run_id@example.com" PHONE_LINE_PASSWORD=$(password)
PHONE_LINE_SECRET="whsec_$(openssl rand -base64 32)"
export APP_URL=http://localhost:5173
export CALL_CENTER_URL="$APP_URL/api/functions/phone-line" CALL_CENTER_SECRET=$PHONE_LINE_SECRET
create() { (cd "$root" && bun run --silent protobase users create "$1" --role "$2" --password-stdin <<<"$3" >/dev/null); }
create "$ADMIN_EMAIL" admin "$ADMIN_PASSWORD"
create "$STAFF_EMAIL" agent "$STAFF_PASSWORD"
create "$PHONE_LINE_EMAIL" phone_line "$PHONE_LINE_PASSWORD"

# the app, on this stack's LiveKit server; an app already on the port would answer in its place
if curl -s -o /dev/null "$APP_URL/"; then
  echo "something answers on $APP_URL already: stop your own bun run dev first" >&2
  exit 1
fi
(cd "$root" && LIVEKIT_URL=ws://127.0.0.1:7880 LIVEKIT_API_KEY=$LIVEKIT_API_KEY \
  LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET PHONE_LINE_SECRET=$PHONE_LINE_SECRET \
  exec bun run dev >"$out/app.log" 2>&1) &
app=$!
trap 'kill "$app" 2>/dev/null || true' EXIT
for _ in $(seq 60); do curl -sf -o /dev/null "$APP_URL/" && break; sleep 1; done
curl -sf -o /dev/null "$APP_URL/" || { echo "the app did not start, see $out/app.log" >&2; exit 1; }
DATABASE_URL=${DATABASE_URL:-$(grep -E '^DATABASE_URL=' "$root/.env" | cut -d= -f2-)}
export DATABASE_URL STAFF_PAGE="$out/staff-page.js" CLIPS_DIR="$phone/tests/sip_call"
bun build "$phone/tests/bridge_call/staff-page.ts" --target browser --format esm --outfile "$STAFF_PAGE" >/dev/null

docker compose --profile test build
docker compose up -d
started() { docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q "$1")"; }
registered() { docker compose logs --since "$(started "$1")" "$1" | grep -q "registered worker"; }
wait_registered() {
  for _ in $(seq 60); do registered "$1" && return; sleep 1; done
  echo "the $1 did not register" >&2
  exit 1
}
wait_registered agent
wait_registered bridge

driver() { bun "$phone/tests/bridge_call/driver.ts" "$out" "$@"; }
# the staff side of a call in the background, then the caller's: call <name> <seconds> <lines>
call() {
  name=$1
  shift
  driver "$name" >"$out/$name-driver.log" 2>&1 &
  staff=$!
  until [ -e "$out/$name-ready" ] || ! kill -0 "$staff" 2>/dev/null; do sleep 0.2; done
  docker compose --profile test run --rm --no-deps sip-call sh bridge_call.sh "$name" "$@"
  wait "$staff" || { echo "the staff side of $name failed, see $out/$name-driver.log" >&2; exit 1; }
}

call hold 70 8:person.wav 50:caller-line.wav
driver sessions
driver revoke
driver sessions
call staff-first 60 16:person.wav 30:caller-line.wav
driver sessions

# the bridge's log of the calls above, before it is recreated
docker compose logs bridge >"$out/bridge.log"

# a wrong password: the bridge gives up on the call, which stays with the assistant
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# the bridge gets its own password back however this part ends, and the run keeps its status
restore_bridge() { docker compose up -d --no-deps --force-recreate bridge >/dev/null 2>&1 || true; }
trap 'status=$?; restore_bridge; kill "$app" 2>/dev/null || true; exit "$status"' EXIT
PHONE_LINE_PASSWORD="wrong-$PHONE_LINE_PASSWORD" docker compose up -d --no-deps --force-recreate bridge
wait_registered bridge
docker compose --profile test run --rm --no-deps sip-call sh bridge_call.sh wrong-password 20
sleep 10
docker compose logs --since "$since" bridge >"$out/wrong-password-bridge.log"
restore_bridge
trap 'kill "$app" 2>/dev/null || true' EXIT

docker compose logs agent >"$out/agent.log"
checked=0
uv run python tests/bridge_call/check_bridge_call.py "$out" "$phone/tests/sip_call" || checked=1
uv run python tests/bridge_call/check_sign_in.py "$out" || checked=1
exit "$checked"
