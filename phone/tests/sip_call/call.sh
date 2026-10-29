#!/bin/sh
# Inside the sip-call container: two refused calls, then one call the agent must greet and answer.
# SIP_TARGET is LiveKit SIP's address, CAPTURE_INTERFACE the one tcpdump records on. Writes the SIPp
# logs, the recorded call and agent.wav to /out.
set -u

target=${SIP_TARGET:-livekit:5060}
interface=${CAPTURE_INTERFACE:-eth0}
media_port=6000
username=$(python3 -c 'import json; print(json.load(open("inbound-trunk.json"))["auth_username"])')
password=$(python3 -c 'import json; print(json.load(open("inbound-trunk.json"))["auth_password"])')

call() {
  target=$1
  scenario=$2
  shift 2
  sipp "$target" -sf "$scenario.xml" -s agent -mp "$media_port" -m 1 -l 1 -timeout 90 -nostdin \
    -trace_err -error_file "/out/$scenario-errors.log" "$@" > "/out/$scenario.log" 2>&1
  status=$?
  echo "$scenario: sipp exited $status"
  return $status
}

# records the caller's media while a call runs: record <pcap> <call arguments>
record() {
  pcap=$1
  shift
  tcpdump -i "$interface" -p -U -w "$pcap" udp portrange "$media_port-$((media_port + 9))" \
    2>> /out/tcpdump.log &
  capture=$!
  sleep 1
  call "$@"
  called=$?
  sleep 1
  kill "$capture"
  wait "$capture"
  return $called
}

call "$target" unauthenticated || exit 1
call "$target" wrong-password -au "$username" -ap "wrong-$password" || exit 1

record /out/call.pcap "$target" call -au "$username" -ap "$password"
called=$?
python3 check_call.py /out/call.pcap "$media_port" /out
checked=$?

[ "$called" -eq 0 ] && [ "$checked" -eq 0 ]
