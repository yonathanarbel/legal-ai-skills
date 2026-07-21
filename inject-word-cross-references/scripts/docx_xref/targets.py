from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from .models import BookmarkTarget, FootnoteTarget, HeadingTarget
from .namespaces import NS, qn
from .package import DocxPackage


@dataclass(frozen=True)
class EffectiveRange:
    part: str
    parent: etree._Element
    first: etree._Element
    last: etree._Element


class SemanticTargetModel:
    def __init__(self, package: DocxPackage):
        self.package = package

    def footnote_reference_range(self, target: FootnoteTarget) -> EffectiveRange:
        root = self.package.xml("word/document.xml")
        matches = root.xpath(
            ".//w:footnoteReference[@w:id=$note_id]",
            namespaces=NS,
            note_id=str(target.note_id),
        )
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one main-story footnote mark for id {target.note_id}; "
                f"found {len(matches)}"
            )
        run = matches[0].getparent()
        if run is None or run.tag != qn("w:r"):
            raise ValueError("Footnote reference is not directly contained by a run")
        return EffectiveRange("word/document.xml", run.getparent(), run, run)

    def bookmark_range(self, target: BookmarkTarget) -> tuple[EffectiveRange, int, str]:
        root = self.package.xml("word/document.xml")
        starts = root.xpath(
            ".//w:bookmarkStart[@w:name=$name]", namespaces=NS, name=target.name
        )
        if len(starts) != 1:
            raise ValueError(f"Expected one bookmark named {target.name!r}; found {len(starts)}")
        start = starts[0]
        parent = start.getparent()
        bookmark_id = start.get(qn("w:id"), "")
        siblings = list(parent)
        start_index = siblings.index(start)
        end_index = next(
            (
                index
                for index in range(start_index + 1, len(siblings))
                if siblings[index].tag == qn("w:bookmarkEnd")
                and siblings[index].get(qn("w:id")) == bookmark_id
            ),
            None,
        )
        if end_index is None or end_index == start_index + 1:
            raise ValueError(f"Bookmark {target.name!r} is empty or crosses containers")
        first, last = siblings[start_index + 1], siblings[end_index - 1]
        cache = "".join(
            node.text or ""
            for sibling in siblings[start_index + 1 : end_index]
            for node in sibling.xpath(".//w:t", namespaces=NS)
        )
        return EffectiveRange("word/document.xml", parent, first, last), int(bookmark_id), cache

    def heading_range(self, target: HeadingTarget) -> tuple[EffectiveRange, str]:
        root = self.package.xml("word/document.xml")
        paragraphs = root.xpath("./w:body//w:p", namespaces=NS)
        if target.paragraph_index < 1 or target.paragraph_index > len(paragraphs):
            raise ValueError(
                f"Heading paragraph index {target.paragraph_index} is out of range "
                f"(1..{len(paragraphs)})"
            )
        paragraph = paragraphs[target.paragraph_index - 1]
        content = [
            node
            for node in paragraph
            if node.tag not in {qn("w:pPr"), qn("w:bookmarkStart"), qn("w:bookmarkEnd")}
        ]
        if not content:
            raise ValueError("Heading target paragraph has no bookmarkable content")
        cache = "".join(
            node.text or "" for child in content for node in child.xpath(".//w:t", namespaces=NS)
        )
        return EffectiveRange("word/document.xml", paragraph, content[0], content[-1]), cache


class MarkerRangeSelector:
    """Map a semantic placement to one exact marker-bearing text run."""

    def __init__(self, package: DocxPackage):
        self.package = package

    def locate(self, placement_part: str, marker: str, footnote_id: int | None):
        root = self.package.xml(placement_part)
        scope = root
        if footnote_id is not None:
            matches = root.xpath(
                ".//w:footnote[@w:id=$note_id]", namespaces=NS, note_id=str(footnote_id)
            )
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one referring footnote id {footnote_id} in {placement_part}; "
                    f"found {len(matches)}"
                )
            scope = matches[0]
        matches = []
        for text in scope.xpath(".//w:t", namespaces=NS):
            if marker in (text.text or ""):
                matches.append(text)
        if len(matches) != 1:
            raise ValueError(
                f"Marker {marker!r} must occur in exactly one w:t in {placement_part}; "
                f"found {len(matches)}"
            )
        text = matches[0]
        run = text.getparent()
        if run is None or run.tag != qn("w:r") or len(run.xpath("./w:t", namespaces=NS)) != 1:
            raise ValueError("Marker run must contain exactly one text node")
        return root, run, text
