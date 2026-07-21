#!/usr/bin/env python3
"""Fetch a commit-pinned copy of danepps/bluebook for local agent review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY = "danepps/bluebook"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
LICENSE = "CC-BY-SA-4.0"
FILES = ("README.md", "BluebookDSEStyle.csl", "LICENSE")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def request_bytes(url: str, timeout: float = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "legal-ai-skills-bluebook-review/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def resolve_commit(ref: str) -> str:
    if COMMIT_RE.fullmatch(ref):
        return ref
    encoded = urllib.parse.quote(ref, safe="")
    payload = json.loads(
        request_bytes(f"https://api.github.com/repos/{REPOSITORY}/commits/{encoded}")
    )
    commit = str(payload.get("sha") or "")
    if not COMMIT_RE.fullmatch(commit):
        raise RuntimeError("GitHub did not return a valid commit SHA")
    return commit


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_bundle(output_dir: Path, ref: str) -> dict[str, Any]:
    commit = resolve_commit(ref)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_metadata: dict[str, dict[str, Any]] = {}
    for name in FILES:
        encoded_name = "/".join(urllib.parse.quote(part, safe="") for part in name.split("/"))
        url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{encoded_name}"
        data = request_bytes(url)
        (output_dir / name).write_bytes(data)
        file_metadata[name] = {"url": url, "bytes": len(data), "sha256": sha256(data)}
    metadata = {
        "repository": REPOSITORY,
        "repository_url": REPOSITORY_URL,
        "requested_ref": ref,
        "resolved_commit": commit,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "license": LICENSE,
        "attribution": (
            "Bluebook Style — Epps Version; modifications by Daniel Epps; original "
            "community Bluebook CSL by Bruce D'Arcus and Nancy Sims, with contributions "
            "from Patrick O'Brien."
        ),
        "files": file_metadata,
    }
    (output_dir / "source.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return metadata


def validate_offline(output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "source.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"missing offline metadata: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("repository") != REPOSITORY or metadata.get("license") != LICENSE:
        raise ValueError("offline bundle has unexpected repository or license metadata")
    expected_files = metadata.get("files") or {}
    for name in FILES:
        path = output_dir / name
        if not path.exists():
            raise FileNotFoundError(f"missing offline file: {path}")
        expected = str((expected_files.get(name) or {}).get("sha256") or "")
        actual = sha256(path.read_bytes())
        if not expected or actual != expected:
            raise ValueError(f"offline hash mismatch: {name}")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ref", default="main", help="Branch, tag, or 40-character commit SHA")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate and reuse an existing bundle without network access",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        metadata = validate_offline(args.output_dir) if args.offline else fetch_bundle(
            args.output_dir, args.ref
        )
    except (OSError, ValueError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"fetch_epps_bluebook: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
