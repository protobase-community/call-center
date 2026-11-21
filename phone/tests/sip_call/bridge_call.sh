#!/bin/sh
# Inside the sip-call container, for tests/bridge_call/run.sh: one recorded trunk call whose caller
# says each line at its second and hangs up after <seconds>. Writes /out/<name>.pcap and the SIPp
# logs. SIP_TARGET is LiveKit SIP's address, CAPTURE_INTERFACE the one tcpdump records on.
# usage: bridge_call.sh <name> <seconds> [<second>:<clip.wav> ...]
set -eu

name=$1
seconds=$2
shift 2
target=${SIP_TARGET:-livekit:5060}
interface=${CAPTURE_INTERFACE:-eth0}
media_port=6000
username=$(python3 -c 'import json; print(json.load(open("inbound-trunk.json"))["auth_username"])')
password=$(python3 -c 'import json; print(json.load(open("inbound-trunk.json"))["auth_password"])')

python3 timeline.py "/tmp/$name.wav" "$seconds" "$@"
sox "/tmp/$name.wav" -r 8000 -c 1 -e a-law -t raw "/tmp/$name.al"
sed -e "s|TIMELINE|/tmp/$name.al|" -e "s|MILLISECONDS|$((seconds * 1000))|" timeline-call.xml \
  > "/tmp/$name.xml"

tcpdump -i "$interface" -p -U -w "/out/$name.pcap" udp portrange "$media_port-$((media_port + 9))" \
  2>> /out/tcpdump.log &
capture=$!
sleep 1
status=0
sipp "$target" -sf "/tmp/$name.xml" -s agent -mp "$media_port" -m 1 -l 1 -timeout $((seconds + 60)) \
  -nostdin -trace_err -error_file "/out/$name-errors.log" -au "$username" -ap "$password" \
  > "/out/$name.log" 2>&1 || status=$?
sleep 1
kill "$capture"
wait "$capture" || true
echo "$name: sipp exited $status"
exit "$status"
