#!/usr/bin/env bash
# Places SIPp calls into the local stack and checks the agent greets and answers a spoken question.
# usage: phone/tests/sip_call/run.sh   (needs the model's key in phone/.env)
# Leaves the stack running; the agent's side of the call is in phone/sip-call-out/agent.wav.
set -euo pipefail
cd "$(dirname "$0")/../.."

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
docker compose --profile test run --rm sip-call
