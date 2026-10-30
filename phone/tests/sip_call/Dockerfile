# SIPp calls into LiveKit SIP as a trunk would; tcpdump records the call for check_call.py.
# The same image serves the stand-in of the app's phone line.
FROM alpine:3.22
RUN apk add --no-cache sipp tcpdump python3 sox
WORKDIR /sip-call
COPY tests/sip_call/ ./
RUN for clip in *.wav; do sox "$clip" -r 8000 -c 1 -e a-law -t raw "${clip%.wav}.al"; done
# a second of silence, looped after a clip: a caller's phone goes on sending audio, and LiveKit SIP
# hangs up a call that sends none for a while
RUN sox -n -r 8000 -c 1 -e a-law -t raw silence.al trim 0 1
CMD ["sh", "call.sh"]
