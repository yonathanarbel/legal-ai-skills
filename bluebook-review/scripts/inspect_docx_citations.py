#!/usr/bin/env python3
"""Extract note text and citation-field metadata from a DOCX package as JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
NOTE_PARTS = (("footnote", "word/footnotes.xml"), ("endnote", "word/endnotes.xml"))
CITATION_HINT = re.compile(
    r"\b(?:id\.|supra|infra|U\.S\.C\.|S\. Ct\.|F\. ?(?:2d|3d|4th)|L\. Ed\.)\b|§|\b\d+\s+[A-Z][A-Za-z. ]+\s+\d+\b",
    re.IGNORECASE,
)


def parse_xml(package: zipfile.ZipFile, part: str) -> ET.Element:
    try:
        data = package.read(part)
    except KeyError as exc:
        raise FileNotFoundError(f"DOCX part not found: {part}") from exc
    return ET.fromstring(data)


def paragraph_text(paragraph: ET.Element) -> str:
    pieces: list[str] = []
    for node in paragraph.iter():
        if node.tag == W + "t":
            pieces.append(node.text or "")
        elif node.tag == W + "tab":
            pieces.append("\t")
        elif node.tag in {W + "br", W + "cr"}:
            pieces.append("\n")
    return "".join(pieces)


def field_codes(scope: ET.Element) -> list[str]:
    codes = [node.text or "" for node in scope.iter(W + "instrText")]
    codes.extend(node.get(W + "instr", "") for node in scope.iter(W + "fldSimple"))
    return [code.strip() for code in codes if code.strip()]


def describe_paragraph(paragraph: ET.Element, index: int) -> dict[str, Any]:
    text = paragraph_text(paragraph)
    codes = field_codes(paragraph)
    upper_codes = "\n".join(codes).upper()
    return {
        "paragraph_index": index,
        "text": text,
        "field_codes": codes,
        "has_word_field": bool(codes or any(True for _ in paragraph.iter(W + "fldChar"))),
        "has_zotero_field": "ZOTERO" in upper_codes or "CSL_CITATION" in upper_codes,
        "citation_hint": bool(CITATION_HINT.search(text)),
    }


def note_reference_order(document: ET.Element, note_kind: str) -> dict[str, int]:
    tag = W + ("footnoteReference" if note_kind == "footnote" else "endnoteReference")
    order: dict[str, int] = {}
    for node in document.iter(tag):
        note_id = node.get(W + "id")
        if note_id is None or node.get(W + "customMarkFollows") is not None:
            continue
        if note_id not in order:
            order[note_id] = len(order) + 1
    return order


def inspect_docx(source: Path, include_body: bool = False) -> dict[str, Any]:
    with zipfile.ZipFile(source, "r") as package:
        document = parse_xml(package, "word/document.xml")
        result: dict[str, Any] = {
            "source": str(source),
            "notes": [],
            "body": [],
            "warnings": [
                "reference_order is document order, not guaranteed displayed numbering",
                "field detection is structural and does not validate Zotero item metadata",
            ],
        }
        available = set(package.namelist())
        for note_kind, part in NOTE_PARTS:
            if part not in available:
                continue
            order = note_reference_order(document, note_kind)
            root = parse_xml(package, part)
            for note in root.findall(W + note_kind):
                if note.get(W + "type") is not None:
                    continue
                note_id = note.get(W + "id")
                paragraphs = [
                    describe_paragraph(paragraph, index)
                    for index, paragraph in enumerate(note.iter(W + "p"), start=1)
                ]
                result["notes"].append(
                    {
                        "kind": note_kind,
                        "ooxml_id": note_id,
                        "reference_order": order.get(note_id or ""),
                        "paragraphs": paragraphs,
                        "has_zotero_field": any(p["has_zotero_field"] for p in paragraphs),
                    }
                )
        if include_body:
            result["body"] = [
                describe_paragraph(paragraph, index)
                for index, paragraph in enumerate(document.iter(W + "p"), start=1)
            ]
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-body", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = inspect_docx(args.source, args.include_body)
    except (OSError, zipfile.BadZipFile, ET.ParseError, FileNotFoundError) as exc:
        print(f"inspect_docx_citations: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
