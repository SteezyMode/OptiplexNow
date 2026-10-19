#!/usr/bin/env python3
"""Verify an upstream font using its Git blob ID from the pinned commit.

The source URL uses a fixed Google Fonts commit; we also require the exact
file size and Git blob content ID before embedding any downloaded bytes.
No Git executable is needed: Python is already required to package NOW.
"""
import hashlib
from pathlib import Path
import sys


def verify(path: Path, expected_blob: str, expected_size: int) -> bool:
    if len(expected_blob) != 40 or any(ch not in "0123456789abcdef" for ch in expected_blob):
        raise ValueError("Expected a complete lowercase Git SHA-1 blob ID.")
    data = path.read_bytes()
    if len(data) != expected_size:
        return False
    digest = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
    return digest == expected_blob


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: verify_font.py FILE GIT_BLOB_SHA1 EXPECTED_SIZE", file=sys.stderr)
        return 2
    try:
        ok = verify(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
    except (ValueError, OSError) as exc:
        print("Font verification failed: " + str(exc), file=sys.stderr)
        return 1
    if not ok:
        print("Font verification failed: downloaded bytes differ from pinned upstream blob", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
