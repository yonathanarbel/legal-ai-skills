"""Extract bookmark and complex-field structures from a DOCX as stable JSON."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def simplify(element: etree._Element) -> dict:
    attributes = {
        etree.QName(key).localname: value
        for key, value in sorted(element.attrib.items())
        if etree.QName(key).localname not in {"rsidR", "rsidRPr", "rsidP", "rsidDel"}
    }
    result: dict = {"tag": etree.QName(element).localname}
    if attributes:
        result["attributes"] = attributes
    if element.text is not None:
        result["text"] = element.text
    children = [simplify(child) for child in element]
    if children:
        result["children"] = children
    return result


def dump(path: Path) -> dict:
    output: dict = {"document": path.name, "parts": {}}
    with zipfile.ZipFile(path) as package:
        for name in package.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            root = etree.fromstring(package.read(name))
            bookmarks = root.xpath(".//w:bookmarkStart | .//w:bookmarkEnd", namespaces={"w": W})
            field_runs = root.xpath(".//w:r[w:fldChar or w:instrText]", namespaces={"w": W})
            simple_fields = root.xpath(".//w:fldSimple", namespaces={"w": W})
            if bookmarks or field_runs or simple_fields:
                output["parts"][name] = {
                    "bookmarks": [simplify(node) for node in bookmarks],
                    "field_runs": [simplify(node) for node in field_runs],
                    "simple_fields": [simplify(node) for node in simple_fields],
                }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(dump(args.docx), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
