from __future__ import annotations

import json
import re

_SINGLE_JSON_FENCE = re.compile(r"\A\s*```(?:json)?\s*\n(?P<body>.*?)\n```\s*\Z", re.DOTALL)


def parse_strict_json_content(content: str) -> object:
    """Parse raw JSON or one JSON-only Markdown fence; reject surrounding prose."""
    try:
        return json.loads(content)
    except json.JSONDecodeError as raw_error:
        match = _SINGLE_JSON_FENCE.fullmatch(content)
        if match is None:
            raise raw_error
        return json.loads(match.group("body"))
