from __future__ import annotations

import json
from pathlib import Path

from .bookmarks import Bookmark, BookmarkRegistry
from .evaluator import FootnoteNumberingEvaluator
from .models import (
    BookmarkTarget,
    CrossReferenceRequest,
    Evaluation,
    FootnoteTarget,
    HeadingTarget,
    ManifestEntry,
    ReferenceKind,
)
from .package import DocxPackage
from .namespaces import NS
from .serializer import DonorFieldSerializer, replace_marker_run
from .targets import MarkerRangeSelector, SemanticTargetModel
from .validator import validate_package


class CrossReferenceInjector:
    def __init__(self, serializer: DonorFieldSerializer | None = None):
        self.serializer = serializer or DonorFieldSerializer()

    def inject(
        self,
        source: Path,
        destination: Path,
        requests: list[CrossReferenceRequest],
        manifest_path: Path | None = None,
    ) -> list[ManifestEntry]:
        package = DocxPackage(source)
        registry = BookmarkRegistry(package)
        manifest: list[ManifestEntry] = []
        for index, request in enumerate(requests, start=1):
            targets = SemanticTargetModel(package)
            if isinstance(request.target, FootnoteTarget):
                if request.kind not in {
                    ReferenceKind.FOOTNOTE_NUMBER,
                    ReferenceKind.FORMATTED_FOOTNOTE_NUMBER,
                    ReferenceKind.POSITION,
                }:
                    raise ValueError(f"Reference kind {request.kind.value} does not match footnote target")
                target_range = targets.footnote_reference_range(request.target)
                bookmark = registry.ensure(target_range)
                evaluation = FootnoteNumberingEvaluator(package).evaluate(
                    request.target, request.kind
                )
                target_manifest = {"kind": "footnote", "id": request.target.note_id}
            elif isinstance(request.target, BookmarkTarget):
                if request.kind != ReferenceKind.BOOKMARK_TEXT:
                    raise ValueError("Bookmark targets require kind 'bookmark-text'")
                if not request.hyperlink:
                    raise ValueError("Non-hyperlinked bookmark REF donor is not yet harvested")
                target_range, bookmark_id, cache = targets.bookmark_range(request.target)
                bookmark = Bookmark(request.target.name, bookmark_id, True)
                evaluation = Evaluation(cache)
                target_manifest = {"kind": "bookmark", "name": request.target.name}
            elif isinstance(request.target, HeadingTarget):
                if request.kind != ReferenceKind.HEADING_TEXT:
                    raise ValueError("Heading targets require kind 'heading-text'")
                if not request.hyperlink:
                    raise ValueError("Non-hyperlinked heading REF donor is not yet harvested")
                target_range, cache = targets.heading_range(request.target)
                bookmark = registry.ensure(target_range)
                evaluation = Evaluation(cache)
                target_manifest = {
                    "kind": "heading",
                    "paragraph_index": request.target.paragraph_index,
                }
            else:
                raise TypeError(f"Unsupported target: {request.target!r}")
            registry.commit()
            selector = MarkerRangeSelector(package)
            placement_root, run, text = selector.locate(
                request.placement.part,
                request.placement.marker,
                request.placement.footnote_id,
            )
            insertion_rpr = run.find("w:rPr", namespaces=NS)
            field_nodes, instruction = self.serializer.render(
                request.kind,
                request.hyperlink,
                bookmark.name,
                evaluation.value,
                insertion_rpr,
            )
            replace_marker_run(run, text, request.placement.marker, field_nodes)
            package.replace_xml(request.placement.part, placement_root)
            warnings = list(evaluation.warnings)
            if request.kind.value == "position":
                warnings.append(
                    "Word's harvested position donor contains no separate/cache until evaluation."
                )
            manifest.append(
                ManifestEntry(
                    index=index,
                    reference_kind=request.kind.value,
                    location={
                        "part": request.placement.part,
                        "footnote_id": request.placement.footnote_id,
                        "marker": request.placement.marker,
                    },
                    target=target_manifest,
                    bookmark_name=bookmark.name,
                    bookmark_id=bookmark.bookmark_id,
                    bookmark_reused=bookmark.reused,
                    computed_cache=evaluation.value,
                    confidence=evaluation.confidence,
                    warnings=warnings,
                    field_instruction=instruction,
                )
            )
        report = validate_package(package)
        if not report.ok:
            raise ValueError("Injected package failed validation: " + "; ".join(report.errors))
        package.write(destination)
        manifest_path = manifest_path or Path(str(destination) + ".xref-manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "source": str(source),
                    "output": str(destination),
                    "references": [entry.to_dict() for entry in manifest],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return manifest
