from __future__ import annotations

import copy
import re
from importlib import resources

from lxml import etree

from .models import ReferenceKind
from .namespaces import NS, PARSER, qn

FIELD_TARGET_PATTERN = re.compile(r"^(\s*(?:NOTEREF|REF)\s+)(\S+)")


class DonorFieldSerializer:
    """Default serializer: transplant Word-authored donor nodes by substitution."""

    def _donor_name(self, kind: ReferenceKind, hyperlink: bool) -> str:
        base = {
            ReferenceKind.FOOTNOTE_NUMBER: "noteref",
            ReferenceKind.FORMATTED_FOOTNOTE_NUMBER: "noteref_f",
            ReferenceKind.POSITION: "noteref_p",
            ReferenceKind.BOOKMARK_TEXT: "ref_bookmark",
            ReferenceKind.HEADING_TEXT: "ref_heading",
        }[kind]
        return f"{base}{'_h' if hyperlink else ''}.xml"

    def render(
        self,
        kind: ReferenceKind,
        hyperlink: bool,
        bookmark_name: str,
        cached_value: str,
        insertion_rpr: etree._Element | None = None,
    ) -> tuple[list[etree._Element], str]:
        name = self._donor_name(kind, hyperlink)
        donor = resources.files("docx_xref").joinpath("donors", name).read_bytes()
        root = etree.fromstring(donor, parser=PARSER)
        nodes = [copy.deepcopy(node) for node in root]
        if insertion_rpr is not None:
            for node in nodes:
                runs = [node] if node.tag == qn("w:r") else node.xpath(".//w:r", namespaces=NS)
                for run in runs:
                    donor_rpr = run.find("w:rPr", namespaces=NS)
                    merged = copy.deepcopy(insertion_rpr)
                    if donor_rpr is not None:
                        # Donor-only semantic properties (notably the formatted
                        # FootnoteReference style) override the insertion format.
                        existing_tags = {child.tag for child in donor_rpr}
                        for child in list(merged):
                            if child.tag in existing_tags:
                                merged.remove(child)
                        for child in reversed(list(donor_rpr)):
                            merged.insert(0, copy.deepcopy(child))
                        run.remove(donor_rpr)
                    run.insert(0, merged)
        instruction = ""
        for node in nodes:
            simple = node if node.tag == qn("w:fldSimple") else None
            if simple is not None:
                raw = simple.get(qn("w:instr"), "")
                instruction = FIELD_TARGET_PATTERN.sub(rf"\g<1>{bookmark_name}", raw)
                simple.set(qn("w:instr"), instruction)
            for text in node.xpath(".//w:instrText", namespaces=NS):
                instruction = FIELD_TARGET_PATTERN.sub(
                    rf"\g<1>{bookmark_name}", text.text or ""
                )
                text.text = instruction
        result_texts: list[etree._Element] = []
        separate_seen = False
        for node in nodes:
            if node.tag == qn("w:fldSimple"):
                result_texts.extend(node.xpath(".//w:t", namespaces=NS))
                continue
            for descendant in node.iter():
                if descendant.tag == qn("w:fldChar") and descendant.get(
                    qn("w:fldCharType")
                ) == "separate":
                    separate_seen = True
                elif separate_seen and descendant.tag == qn("w:t"):
                    result_texts.append(descendant)
        if result_texts:
            if len(result_texts) != 1:
                raise ValueError(f"Donor {name} has ambiguous cached result text")
            result_texts[0].text = cached_value
        return nodes, instruction


def _set_text(text: etree._Element, value: str) -> None:
    text.text = value
    if value.startswith(" ") or value.endswith(" "):
        text.set(qn("xml:space"), "preserve")
    else:
        text.attrib.pop(qn("xml:space"), None)


def replace_marker_run(
    run: etree._Element,
    text: etree._Element,
    marker: str,
    field_nodes: list[etree._Element],
) -> None:
    allowed = {qn("w:rPr"), qn("w:t")}
    if any(child.tag not in allowed for child in run):
        raise ValueError("Marker run contains non-text content and cannot be split safely")
    parent = run.getparent()
    if parent is None:
        raise ValueError("Detached marker run")
    siblings = list(parent)
    index = siblings.index(run)
    if index and siblings[index - 1].tag == qn("w:bookmarkStart"):
        raise ValueError("Marker begins at a bookmark opening edge; choose a later insertion point")
    original = text.text or ""
    before, after = original.split(marker, 1)
    replacements: list[etree._Element] = []
    if before:
        leading = copy.deepcopy(run)
        _set_text(leading.find("w:t", namespaces=NS), before)
        replacements.append(leading)
    replacements.extend(field_nodes)
    if after:
        trailing = copy.deepcopy(run)
        _set_text(trailing.find("w:t", namespaces=NS), after)
        replacements.append(trailing)
    parent.remove(run)
    for offset, replacement in enumerate(replacements):
        parent.insert(index + offset, replacement)
