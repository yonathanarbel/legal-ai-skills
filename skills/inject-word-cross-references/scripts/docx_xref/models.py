from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ReferenceKind(str, Enum):
    FOOTNOTE_NUMBER = "footnote-number"
    FORMATTED_FOOTNOTE_NUMBER = "formatted-footnote-number"
    POSITION = "position"
    BOOKMARK_TEXT = "bookmark-text"
    HEADING_TEXT = "heading-text"


@dataclass(frozen=True)
class FootnoteTarget:
    note_id: int


@dataclass(frozen=True)
class BookmarkTarget:
    name: str


@dataclass(frozen=True)
class HeadingTarget:
    paragraph_index: int


@dataclass(frozen=True)
class MarkerPlacement:
    part: str
    marker: str
    footnote_id: int | None = None


@dataclass(frozen=True)
class CrossReferenceRequest:
    target: FootnoteTarget | BookmarkTarget | HeadingTarget
    placement: MarkerPlacement
    kind: ReferenceKind = ReferenceKind.FOOTNOTE_NUMBER
    hyperlink: bool = True


@dataclass
class Evaluation:
    value: str
    confidence: str = "exact"
    warnings: list[str] = field(default_factory=list)


@dataclass
class ManifestEntry:
    index: int
    reference_kind: str
    location: dict[str, Any]
    target: dict[str, Any]
    bookmark_name: str
    bookmark_id: int
    bookmark_reused: bool
    computed_cache: str
    confidence: str
    warnings: list[str]
    field_instruction: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
