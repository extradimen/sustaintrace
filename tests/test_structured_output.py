import json

import pytest

from esg_reliable_discovery.structured_output import parse_strict_json_content


def test_parses_raw_json():
    assert parse_strict_json_content('{"status":"ok"}') == {"status": "ok"}


def test_parses_single_json_fence():
    assert parse_strict_json_content('```json\n{"status":"ok"}\n```') == {"status": "ok"}


def test_rejects_prose_around_fenced_json():
    with pytest.raises(json.JSONDecodeError):
        parse_strict_json_content('Result:\n```json\n{"status":"ok"}\n```')
