from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from lxml import etree

from .namespaces import NS, qn
from .package import DocxPackage


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_package(package: DocxPackage) -> ValidationReport:
    report = ValidationReport()
    starts: list[tuple[str, str, str]] = []
    ends: list[tuple[str, str]] = []
    names: list[str] = []
    for part in package.names():
        if not part.endswith(".xml"):
            continue
        try:
            root = package.xml(part)
        except etree.XMLSyntaxError as exc:
            report.errors.append(f"{part}: malformed XML: {exc}")
            continue
        if part.startswith("word/"):
            for node in root.xpath(".//w:bookmarkStart", namespaces=NS):
                bookmark_id = node.get(qn("w:id"), "")
                name = node.get(qn("w:name"), "")
                starts.append((part, bookmark_id, name))
                names.append(name)
            for node in root.xpath(".//w:bookmarkEnd", namespaces=NS):
                ends.append((part, node.get(qn("w:id"), "")))
            stack: list[str] = []
            for fld in root.xpath(".//w:fldChar", namespaces=NS):
                fld_type = fld.get(qn("w:fldCharType"), "")
                if fld.get(qn("w:dirty")) is not None:
                    report.errors.append(f"{part}: w:dirty is forbidden")
                if fld_type == "begin":
                    stack.append("begin")
                elif fld_type == "separate":
                    if not stack:
                        report.errors.append(f"{part}: field separate without begin")
                    else:
                        stack[-1] = "separate"
                elif fld_type == "end":
                    if not stack:
                        report.errors.append(f"{part}: field end without begin")
                    else:
                        stack.pop()
            if stack:
                report.errors.append(f"{part}: {len(stack)} unclosed complex field(s)")
            if root.xpath(".//w:updateFields", namespaces=NS):
                report.errors.append(f"{part}: w:updateFields is forbidden")
    start_keys = [(part, bookmark_id) for part, bookmark_id, _ in starts]
    for key, count in Counter(start_keys).items():
        if count != 1:
            report.errors.append(f"{key[0]}: duplicate bookmark start id {key[1]}")
    for bookmark_id, count in Counter(key[1] for key in start_keys).items():
        if bookmark_id and count != 1:
            report.errors.append(f"Bookmark id {bookmark_id} is not package-global unique")
    for key, count in Counter(ends).items():
        if count != 1:
            report.errors.append(f"{key[0]}: duplicate bookmark end id {key[1]}")
    if Counter(start_keys) != Counter(ends):
        report.errors.append("Bookmark start/end pairs do not balance by story part and id")
    for name, count in Counter(names).items():
        if name and count != 1:
            report.errors.append(f"Duplicate bookmark name {name!r}")
    return report
