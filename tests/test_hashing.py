from esg_reliable_discovery.hashing import canonical_json, sha256_json


def test_canonical_json_is_key_order_independent():
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_json(left) == sha256_json(right)
