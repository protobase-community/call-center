"""Serves the phone line stand-in on 127.0.0.1 at the app's address of the function, and checks
each request's signature first, as the app does.

usage: stand_in_server.py <port> <log file>   (CALL_CENTER_SECRET in the environment)

Appends one JSON line per request to <log file>: its method, path, status and answer, never its
body, which holds the caller's customer number and PIN.
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from phone_line_stand_in import PhoneLine
from stand_in_signature import Refused, SignatureCheck, secret_key

FUNCTION_PATH = "/api/functions/phone-line"


def stand_in_server(port: int, log_path: str, key: bytes) -> HTTPServer:
    line = PhoneLine()
    signatures = SignatureCheck(key)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._answer()

        def do_POST(self) -> None:
            self._answer()

        def _answer(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            text = self.rfile.read(length).decode()
            path = self.path.removeprefix(FUNCTION_PATH)
            status, answer = self._routed(path, text)

            with open(log_path, "a") as log:
                record = {"method": self.command, "path": path, "status": status, "answer": answer}
                log.write(json.dumps(record) + "\n")

            content = json.dumps(answer).encode()
            problem = "type" in answer
            self.send_response(status)
            self.send_header("content-type", f"application/{'problem+' if problem else ''}json")
            self.send_header("content-length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _routed(self, path: str, text: str) -> tuple[int, dict[str, object]]:
            if not self.path.startswith(FUNCTION_PATH + "/"):
                return 404, {"type": "urn:protobase:problem:not-found"}
            try:
                headers = {name.lower(): value for name, value in self.headers.items()}
                signatures.check(headers, text, time.time())
            except Refused as refused:
                return 401, {"type": f"urn:protobase:problem:{refused.slug}"}
            return line.answer(self.command, path, text)

        def log_message(self, format: str, *args: object) -> None:
            """The log file has each request; nothing goes to stderr."""

    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: stand_in_server.py <port> <log file>")
    open(sys.argv[2], "w").close()
    server = stand_in_server(
        int(sys.argv[1]), sys.argv[2], secret_key(os.environ["CALL_CENTER_SECRET"])
    )
    server.serve_forever()
