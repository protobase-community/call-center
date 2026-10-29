# SIPp calls into LiveKit SIP as a trunk would; tcpdump records the call for check_call.py
FROM alpine:3.22
RUN apk add --no-cache sipp tcpdump python3 sox
WORKDIR /sip-call
COPY tests/sip_call/ ./
RUN sox question.wav -r 8000 -c 1 -e a-law -t raw question.al
CMD ["sh", "call.sh"]
