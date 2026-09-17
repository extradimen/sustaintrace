#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from esg_reliable_discovery.hashing import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checksum_file")
    args = parser.parse_args()
    checksum_path = Path(args.checksum_file)
    failures = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        target = checksum_path.parent / name.strip()
        actual = sha256_file(target)
        if actual != expected:
            failures.append((str(target), expected, actual))
    if failures:
        for target, expected, actual in failures:
            print(f"FAILED {target}: expected {expected}, got {actual}")
        raise SystemExit(1)
    print(f"Verified {checksum_path}")


if __name__ == "__main__":
    main()
