# SIPp calls into LiveKit SIP as a trunk would; tcpdump records the call for check_call.py.
# The same image serves the stand-in of the app's phone line.
FROM alpine:3.22
RUN apk add --no-cache sipp tcpdump python3 sox
WORKDIR /sip-call
COPY tests/sip_call/ ./
RUN for clip in *.wav; do sox "$clip" -r 8000 -c 1 -e a-law -t raw "${clip%.wav}.al"; done
CMD ["sh", "call.sh"]
