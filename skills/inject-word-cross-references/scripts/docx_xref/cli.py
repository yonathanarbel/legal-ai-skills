from __future__ import annotations

import argparse
import json
from pathlib import Path

from .injector import CrossReferenceInjector
from .differential import semantic_signature
from .models import (
    BookmarkTarget,
    CrossReferenceRequest,
    FootnoteTarget,
    HeadingTarget,
    MarkerPlacement,
    ReferenceKind,
)
from .package import DocxPackage
from .validator import validate_package


def _load_requests(path: Path) -> list[CrossReferenceRequest]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_requests = payload.get("references", payload) if isinstance(payload, dict) else payload
    requests = []
    for raw in raw_requests:
        target = raw["target"]
        target_kind = target.get("kind", "footnote")
        if target_kind == "footnote":
            semantic_target = FootnoteTarget(int(target["id"]))
        elif target_kind == "bookmark":
            semantic_target = BookmarkTarget(target["name"])
        elif target_kind == "heading":
            semantic_target = HeadingTarget(int(target["paragraph_index"]))
        else:
            raise ValueError(f"Unsupported target kind: {target_kind}")
        placement = raw["placement"]
        requests.append(
            CrossReferenceRequest(
                target=semantic_target,
                placement=MarkerPlacement(
                    part=placement["part"],
                    marker=placement["marker"],
                    footnote_id=(
                        int(placement["footnote_id"])
                        if placement.get("footnote_id") is not None
                        else None
                    ),
                ),
                kind=ReferenceKind(raw.get("kind", ReferenceKind.FOOTNOTE_NUMBER.value)),
                hyperlink=bool(raw.get("hyperlink", True)),
            )
        )
    return requests


def main() -> None:
    parser = argparse.ArgumentParser(prog="docx-xref")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inject = subparsers.add_parser("inject", help="Inject fields described by a JSON plan")
    inject.add_argument("source", type=Path)
    inject.add_argument("destination", type=Path)
    inject.add_argument("--plan", type=Path, required=True)
    inject.add_argument("--manifest", type=Path)
    validate = subparsers.add_parser("validate", help="Run structural fidelity checks")
    validate.add_argument("docx", type=Path)
    diff = subparsers.add_parser("diff", help="Compare cross-reference semantics")
    diff.add_argument("organic", type=Path)
    diff.add_argument("injected", type=Path)
    args = parser.parse_args()
    if args.command == "inject":
        entries = CrossReferenceInjector().inject(
            args.source, args.destination, _load_requests(args.plan), args.manifest
        )
        print(f"Injected {len(entries)} cross-reference(s) into {args.destination}")
    elif args.command == "validate":
        report = validate_package(DocxPackage(args.docx))
        for warning in report.warnings:
            print(f"warning: {warning}")
        for error in report.errors:
            print(f"error: {error}")
        raise SystemExit(0 if report.ok else 1)
    else:
        organic = semantic_signature(args.organic)
        injected = semantic_signature(args.injected)
        if organic != injected:
            print(json.dumps({"organic": organic, "injected": injected}, indent=2))
            raise SystemExit(1)
        print("Cross-reference semantics match")


if __name__ == "__main__":
    main()
