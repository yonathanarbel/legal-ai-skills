"""Behaviorally Word-compatible DOCX cross-reference injection."""

from .injector import CrossReferenceInjector
from .models import (
    BookmarkTarget,
    CrossReferenceRequest,
    FootnoteTarget,
    HeadingTarget,
    MarkerPlacement,
    ReferenceKind,
)

__all__ = [
    "CrossReferenceInjector",
    "BookmarkTarget",
    "CrossReferenceRequest",
    "FootnoteTarget",
    "HeadingTarget",
    "MarkerPlacement",
    "ReferenceKind",
]
