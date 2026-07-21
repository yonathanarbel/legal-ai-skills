from __future__ import annotations

import secrets
from dataclasses import dataclass

from lxml import etree

from .namespaces import NS, qn
from .package import DocxPackage
from .targets import EffectiveRange


@dataclass(frozen=True)
class Bookmark:
    name: str
    bookmark_id: int
    reused: bool


class BookmarkRegistry:
    """Reuse bookmarks by effective range; mint collision-free hidden refs."""

    def __init__(self, package: DocxPackage):
        self.package = package
        self._roots: dict[str, etree._Element] = {}
        self._ids: set[int] = set()
        self._names: set[str] = set()
        self._modified: dict[str, etree._Element] = {}
        for part in package.names():
            if not part.startswith("word/") or not part.endswith(".xml"):
                continue
            try:
                root = package.xml(part)
            except etree.XMLSyntaxError:
                continue
            self._roots[part] = root
            for start in root.xpath(".//w:bookmarkStart", namespaces=NS):
                raw_id = start.get(qn("w:id"))
                if raw_id is not None:
                    try:
                        self._ids.add(int(raw_id))
                    except ValueError:
                        raise ValueError(f"Non-integer bookmark id {raw_id!r} in {part}")
                name = start.get(qn("w:name"))
                if name:
                    if name in self._names:
                        raise ValueError(f"Duplicate bookmark name {name!r} in package")
                    self._names.add(name)

    def root(self, part: str) -> etree._Element:
        return self._roots[part]

    def _exact_bookmarks(self, target: EffectiveRange) -> list[Bookmark]:
        siblings = list(target.parent)
        first_index = siblings.index(target.first)
        last_index = siblings.index(target.last)
        starts: list[etree._Element] = []
        cursor = first_index - 1
        while cursor >= 0 and siblings[cursor].tag == qn("w:bookmarkStart"):
            starts.append(siblings[cursor])
            cursor -= 1
        ends: dict[str, etree._Element] = {}
        cursor = last_index + 1
        while cursor < len(siblings) and siblings[cursor].tag == qn("w:bookmarkEnd"):
            ends[siblings[cursor].get(qn("w:id"), "")] = siblings[cursor]
            cursor += 1
        found: list[Bookmark] = []
        for start in starts:
            raw_id = start.get(qn("w:id"), "")
            name = start.get(qn("w:name"))
            if raw_id in ends and name:
                found.append(Bookmark(name, int(raw_id), True))
        return sorted(found, key=lambda item: (not item.name.startswith("_Ref"), item.name))

    def ensure(self, target: EffectiveRange) -> Bookmark:
        exact = self._exact_bookmarks(target)
        if exact:
            return exact[0]
        bookmark_id = max(self._ids, default=-1) + 1
        while True:
            name = f"_Ref{secrets.randbelow(1_000_000_000):09d}"
            if name not in self._names:
                break
        start = etree.Element(qn("w:bookmarkStart"))
        start.set(qn("w:id"), str(bookmark_id))
        start.set(qn("w:name"), name)
        end = etree.Element(qn("w:bookmarkEnd"))
        end.set(qn("w:id"), str(bookmark_id))
        first_index = target.parent.index(target.first)
        target.parent.insert(first_index, start)
        last_index = target.parent.index(target.last)
        target.parent.insert(last_index + 1, end)
        self._ids.add(bookmark_id)
        self._names.add(name)
        self._modified[target.part] = target.first.getroottree().getroot()
        return Bookmark(name, bookmark_id, False)

    def commit(self) -> None:
        for part, root in self._modified.items():
            self.package.replace_xml(part, root)
