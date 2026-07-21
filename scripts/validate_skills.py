#!/usr/bin/env python3
"""Perform small dependency-free checks on every public skill folder."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening YAML delimiter")
    try:
        raw, _body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML delimiter") from exc
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def main() -> int:
    failures: list[str] = []
    for folder in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
        skill = folder / "SKILL.md"
        if not skill.exists():
            failures.append(f"{folder.name}: missing SKILL.md")
            continue
        try:
            metadata = parse_frontmatter(skill)
        except ValueError as exc:
            failures.append(f"{folder.name}: {exc}")
            continue
        if set(metadata) != {"name", "description"}:
            failures.append(f"{folder.name}: frontmatter must contain only name and description")
        if metadata.get("name") != folder.name:
            failures.append(f"{folder.name}: frontmatter name does not match folder")
        if not NAME_RE.fullmatch(metadata.get("name", "")):
            failures.append(f"{folder.name}: invalid skill name")
        if len(metadata.get("description", "")) < 40:
            failures.append(f"{folder.name}: description is too short")
        agent = folder / "agents" / "openai.yaml"
        if not agent.exists():
            failures.append(f"{folder.name}: missing agents/openai.yaml")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"Validated {len(list(SKILLS.iterdir()))} skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
