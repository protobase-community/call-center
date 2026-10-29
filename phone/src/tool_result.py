"""The one shape every tool result takes, so a new tool only has to decide what it reports.

A result is a JSON object. A tool that changes state reports it under `changed`, so the model
learns what happened from the result rather than from its instructions; a tool that only reads
reports the facts it read. Changing state reaches the model this way, through a tool, or through
an injected message, never through the instructions, which stay fixed so the prompt caches.
"""

import json


def tool_result(**fields: object) -> str:
    return json.dumps(fields, ensure_ascii=False)
