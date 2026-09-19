#!/usr/bin/env python3
"""Scan CSV snapshots for credential-like strings without printing matched values."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path

PATTERNS = {
    "openai_env_name": re.compile(r"OPENAI_API_KEY"),
    "scopus_env_name": re.compile(r"SCOPUS_API_KEY"),
    "semantic_scholar_env_name": re.compile(r"SEMANTIC_SCHOLAR_API_KEY"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9_-]{20,}"),
    "sk_prefix_candidate": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()

    findings = 0
    for path in sorted(args.root.rglob("*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            reader = csv.DictReader(handle)
            for row_number, row in enumerate(reader, start=2):
                for column, value in row.items():
                    for label, pattern in PATTERNS.items():
                        for match in pattern.finditer(value or ""):
                            token = match.group(0)
                            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
                            looks_like_project_key = token.startswith("sk-proj-")
                            print(
                                f"file={path.as_posix()} row={row_number} column={column} "
                                f"pattern={label} length={len(token)} sha256_prefix={digest} "
                                f"openai_project_key_shape={str(looks_like_project_key).lower()}"
                            )
                            findings += 1
    print(f"candidate_matches={findings}")


if __name__ == "__main__":
    main()
