from __future__ import annotations

import re
from typing import Any

from lxml import etree

from .namespaces import NS, qn
from .package import DocxPackage

HIDDEN_REF = re.compile(r"_Ref\d+")


def _normalize_instruction(value: str) -> str:
    return HIDDEN_REF.sub("_Ref#", value)


def _run_properties(run: etree._Element) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
    properties = run.find("w:rPr", namespaces=NS)
    if properties is None:
        return []
    return [
        (
            etree.QName(child).localname,
            tuple(
                sorted(
                    (etree.QName(key).localname, value)
                    for key, value in child.attrib.items()
                    if not etree.QName(key).localname.startswith("rsid")
                )
            ),
        )
        for child in properties
    ]


def semantic_signature(path) -> dict[str, Any]:
    package = DocxPackage(path)
    result: dict[str, Any] = {"bookmarks": [], "fields": []}
    for part in package.names():
        if not part.startswith("word/") or not part.endswith(".xml"):
            continue
        try:
            root = package.xml(part)
        except etree.XMLSyntaxError:
            continue
        for start in root.xpath(".//w:bookmarkStart", namespaces=NS):
            name = start.get(qn("w:name"), "")
            parent = start.getparent()
            siblings = list(parent)
            start_index = siblings.index(start)
            bookmark_id = start.get(qn("w:id"), "")
            end_index = next(
                (
                    index
                    for index in range(start_index + 1, len(siblings))
                    if siblings[index].tag == qn("w:bookmarkEnd")
                    and siblings[index].get(qn("w:id")) == bookmark_id
                ),
                len(siblings),
            )
            text = "".join(
                node.text or ""
                for sibling in siblings[start_index + 1 : end_index]
                for node in sibling.xpath(".//w:t", namespaces=NS)
            )
            tags = [etree.QName(node).localname for node in siblings[start_index + 1 : end_index]]
            result["bookmarks"].append(
                {
                    "part": part,
                    "name": "_Ref#" if HIDDEN_REF.fullmatch(name) else name,
                    "span_tags": tags,
                    "text": text,
                }
            )
        for simple in root.xpath(".//w:fldSimple", namespaces=NS):
            run = simple.find("w:r", namespaces=NS)
            result["fields"].append(
                {
                    "part": part,
                    "shape": "simple",
                    "instruction": _normalize_instruction(simple.get(qn("w:instr"), "")),
                    "cache": "".join(simple.xpath(".//w:t/text()", namespaces=NS)),
                    "result_properties": _run_properties(run) if run is not None else [],
                }
            )
        for instruction in root.xpath(".//w:instrText", namespaces=NS):
            if not re.match(r"\s*(?:NOTEREF|REF)\s", instruction.text or ""):
                continue
            paragraph = instruction.getparent().getparent()
            siblings = list(paragraph)
            index = siblings.index(instruction.getparent()) + 1
            separated = False
            cache = []
            result_properties = []
            shape = ["begin", "instruction"]
            for node in siblings[index:]:
                fld_type = node.xpath("string(w:fldChar/@w:fldCharType)", namespaces=NS)
                if fld_type == "separate":
                    separated = True
                    shape.append("separate")
                elif fld_type == "end":
                    shape.append("end")
                    break
                elif separated:
                    texts = node.xpath(".//w:t/text()", namespaces=NS)
                    if texts:
                        cache.extend(texts)
                        result_properties.extend(_run_properties(node))
            result["fields"].append(
                {
                    "part": part,
                    "shape": shape,
                    "instruction": _normalize_instruction(instruction.text or ""),
                    "cache": "".join(cache),
                    "result_properties": result_properties,
                }
            )
    return result
