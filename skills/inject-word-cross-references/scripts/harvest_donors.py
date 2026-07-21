"""Harvest exact Word-authored field runs into serializer donor files."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def harvest(docx: Path, output: Path) -> None:
    candidates = []
    with zipfile.ZipFile(docx) as package:
        for part in ("word/document.xml", "word/footnotes.xml"):
            if part not in package.namelist():
                continue
            root = etree.fromstring(package.read(part))
            candidates.extend(root.xpath(
        ".//w:instrText[contains(., 'NOTEREF') or starts-with(normalize-space(.), 'REF ')]"
        " | .//w:fldSimple[contains(@w:instr, 'NOTEREF') or "
        "starts-with(normalize-space(@w:instr), 'REF ')]",
        namespaces=NS,
            ))
    if len(candidates) != 1:
        raise ValueError(f"Expected one cross-reference field in {docx}, found {len(candidates)}")
    selected = candidates[0]
    if selected.tag == f"{{{W}}}fldSimple":
        wrapper = etree.Element(f"{{{W}}}donor", nsmap={"w": W})
        wrapper.append(selected)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(etree.tostring(wrapper, xml_declaration=True, encoding="UTF-8"))
        return
    run = selected.getparent()
    parent = run.getparent()
    index = parent.index(run)
    start = index - 1
    if start < 0 or parent[start].xpath(
        "string(w:fldChar/@w:fldCharType)", namespaces=NS
    ) != "begin":
        raise ValueError(f"Instruction is not preceded by field begin in {docx}")
    end = index + 1
    while end < len(parent) and parent[end].xpath(
        "string(w:fldChar/@w:fldCharType)", namespaces=NS
    ) != "end":
        end += 1
    if end >= len(parent):
        raise ValueError(f"Field has no end in {docx}")
    nodes = list(parent)[start : end + 1]
    types = [
        node.xpath("string(w:fldChar/@w:fldCharType)", namespaces=NS)
        for node in nodes
        if node.find(f"{{{W}}}fldChar") is not None
    ]
    if types not in (["begin", "separate", "end"], ["begin", "end"]):
        raise ValueError(f"Unexpected field shape in {docx}: {types}")
    wrapper = etree.Element(f"{{{W}}}donor", nsmap={"w": W})
    for node in nodes:
        wrapper.append(node)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(etree.tostring(wrapper, xml_declaration=True, encoding="UTF-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("organic_dir", type=Path, nargs="?", default=Path("corpus/organic"))
    parser.add_argument("donor_dir", type=Path, nargs="?", default=Path("corpus/donors"))
    args = parser.parse_args()
    for docx in sorted(args.organic_dir.glob("*.docx")):
        harvest(docx, args.donor_dir / f"{docx.stem}.xml")
        print(args.donor_dir / f"{docx.stem}.xml")


if __name__ == "__main__":
    main()
