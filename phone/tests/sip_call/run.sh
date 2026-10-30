#!/usr/bin/env bash
# Places SIPp calls into the local stack and checks the agent greets and answers a spoken question,
# then verifies a caller by keypad, a wrong PIN first, and opens their ticket, and puts a caller who
# asks for a person on hold with music.
# usage: phone/tests/sip_call/run.sh   (needs the model's key in phone/.env)
# Leaves the stack running; the agent's side of the first call is in phone/sip-call-out/agent.wav,
# of the call that asks for a person in phone/sip-call-out/person-agent.wav,
# and what the stand-in of the app's phone line answered in phone/sip-call-out/phone-line.jsonl.
set -euo pipefail
cd "$(dirname "$0")/../.."

# the agent calls the stand-in, with a secret of this run, whatever phone/.env names
export CALL_CENTER_URL=http://127.0.0.1:8090/api/functions/phone-line
CALL_CENTER_SECRET="whsec_$(openssl rand -base64 32)"
export CALL_CENTER_SECRET

# build everything first: a build during run makes a new agent image and restarts the agent
docker compose --profile test build
docker compose up -d

# only the running container's logs: up may just have restarted the agent
started=$(docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q agent)")
registered() { docker compose logs --since "$started" agent | grep -q "registered worker"; }
for _ in $(seq 60); do
  registered && break
  sleep 1
done
registered || { echo "the agent did not register" >&2; exit 1; }

mkdir -p sip-call-out
# a new stand-in, with no calls from an earlier run
docker compose --profile test up -d --force-recreate phone-line-stand-in
docker compose --profile test run --rm sip-call
