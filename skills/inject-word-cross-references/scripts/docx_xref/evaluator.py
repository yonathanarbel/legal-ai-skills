from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from .models import Evaluation, FootnoteTarget, ReferenceKind
from .namespaces import NS, qn
from .package import DocxPackage


@dataclass(frozen=True)
class NumberingConfig:
    start: int = 1
    restart: str = "continuous"
    number_format: str = "decimal"
    explicit_start: bool = False


def _property(element: etree._Element | None, name: str) -> str | None:
    if element is None:
        return None
    found = element.find(f"w:{name}", namespaces=NS)
    return found.get(qn("w:val")) if found is not None else None


def _config(base: NumberingConfig, footnote_pr: etree._Element | None) -> NumberingConfig:
    raw_start = _property(footnote_pr, "numStart")
    return NumberingConfig(
        start=int(raw_start) if raw_start is not None else base.start,
        restart=_property(footnote_pr, "numRestart") or base.restart,
        number_format=_property(footnote_pr, "numFmt") or base.number_format,
        explicit_start=raw_start is not None,
    )


def _roman(value: int) -> str:
    if value <= 0 or value >= 4000:
        return str(value)
    pairs = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    result = []
    for amount, symbol in pairs:
        while value >= amount:
            result.append(symbol)
            value -= amount
    return "".join(result)


def _letters(value: int) -> str:
    if value <= 0:
        return str(value)
    result = []
    while value:
        value, remainder = divmod(value - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def render_number(value: int, number_format: str) -> str:
    if number_format == "decimal":
        return str(value)
    if number_format == "upperRoman":
        return _roman(value)
    if number_format == "lowerRoman":
        return _roman(value).lower()
    if number_format == "upperLetter":
        return _letters(value)
    if number_format == "lowerLetter":
        return _letters(value).lower()
    if number_format == "chicago":
        symbols = ("*", "†", "‡", "§", "‖", "#")
        symbol = symbols[(value - 1) % len(symbols)]
        return symbol * ((value - 1) // len(symbols) + 1)
    raise ValueError(f"Unsupported footnote number format: {number_format}")


class FootnoteNumberingEvaluator:
    def __init__(self, package: DocxPackage):
        self.package = package

    def _global_config(self) -> NumberingConfig:
        if not self.package.has("word/settings.xml"):
            return NumberingConfig()
        settings = self.package.xml("word/settings.xml")
        return _config(NumberingConfig(), settings.find("w:footnotePr", namespaces=NS))

    def _special_ids(self) -> set[str]:
        if not self.package.has("word/footnotes.xml"):
            return set()
        root = self.package.xml("word/footnotes.xml")
        return {
            note.get(qn("w:id"), "")
            for note in root.xpath("./w:footnote[@w:type]", namespaces=NS)
        }

    def _sections(self):
        document = self.package.xml("word/document.xml")
        body = document.find("w:body", namespaces=NS)
        if body is None:
            raise ValueError("word/document.xml has no body")
        groups: list[tuple[list[etree._Element], etree._Element | None]] = []
        current: list[etree._Element] = []
        for child in body:
            if child.tag == qn("w:sectPr"):
                groups.append((current, child))
                current = []
                continue
            current.append(child)
            boundary = child.find("./w:pPr/w:sectPr", namespaces=NS)
            if boundary is not None:
                groups.append((current, boundary))
                current = []
        if current or not groups:
            groups.append((current, None))
        return groups

    def evaluate(self, target: FootnoteTarget, kind: ReferenceKind) -> Evaluation:
        if kind == ReferenceKind.POSITION:
            return Evaluation(
                "above",
                "degraded",
                ["Position references require pagination; cached 'above' is a best guess."],
            )
        special = self._special_ids()
        global_config = self._global_config()
        continuous_next = global_config.start
        warnings: list[str] = []
        for section_index, (children, sect_pr) in enumerate(self._sections(), start=1):
            section_pr = (
                sect_pr.find("w:footnotePr", namespaces=NS) if sect_pr is not None else None
            )
            config = _config(global_config, section_pr)
            if config.restart == "eachPage":
                warnings.append(
                    f"Section {section_index} uses per-page footnote restart; layout is required."
                )
            if config.restart in {"eachSect", "eachPage"} or config.explicit_start:
                next_value = config.start
            else:
                next_value = continuous_next
            for child in children:
                for ref in child.xpath(".//w:footnoteReference", namespaces=NS):
                    note_id = ref.get(qn("w:id"), "")
                    if note_id in special or ref.get(qn("w:customMarkFollows")) is not None:
                        continue
                    if note_id == str(target.note_id):
                        confidence = "degraded" if config.restart == "eachPage" else "exact"
                        return Evaluation(
                            render_number(next_value, config.number_format), confidence, warnings
                        )
                    next_value += 1
            continuous_next = next_value
        raise ValueError(f"Automatic footnote target id {target.note_id} was not found")
