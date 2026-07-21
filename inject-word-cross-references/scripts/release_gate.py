"""Microsoft Word differential release gate (Windows workstation only)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WD_COLLAPSE_START = 1
WD_EXPORT_PDF = 17


def update_all_stories(document) -> None:
    for story_type in range(1, 18):
        try:
            story = document.StoryRanges(story_type)
        except Exception:
            continue
        while story is not None:
            story.Fields.Update()
            story = story.NextStoryRange


def story_text(document) -> dict[str, str]:
    result = {}
    for story_type in range(1, 18):
        try:
            story = document.StoryRanges(story_type)
        except Exception:
            continue
        index = 0
        while story is not None:
            result[f"{story_type}:{index}"] = story.Text
            story = story.NextStoryRange
            index += 1
    return result


def mutate(document, operation: str) -> None:
    if operation == "baseline":
        return
    if operation == "renumber":
        insertion = document.Range(0, 0)
        document.Footnotes.Add(insertion, Text="Preceding release-gate note.")
    elif operation == "delete":
        document.Footnotes(1).Delete()
    elif operation == "convert":
        document.Footnotes.Convert()
        document.Endnotes.Convert()
    elif operation == "track-accept":
        document.TrackRevisions = True
        document.Footnotes(1).Reference.Delete()
        document.Revisions.AcceptAll()
        document.TrackRevisions = False
    elif operation == "track-reject":
        document.TrackRevisions = True
        document.Footnotes(1).Reference.Delete()
        document.Revisions.RejectAll()
        document.TrackRevisions = False
    else:
        raise ValueError(operation)


def exercise(word, source: Path, destination: Path, operation: str) -> dict:
    shutil.copy2(source, destination)
    doc = word.Documents.Open(
        str(destination.resolve()),
        ConfirmConversions=False,
        ReadOnly=False,
        AddToRecentFiles=False,
        OpenAndRepair=False,
        NoEncodingDialog=True,
    )
    try:
        mutate(doc, operation)
        update_all_stories(doc)
        doc.Save()
        pdf = destination.with_suffix(f".{operation}.pdf")
        doc.ExportAsFixedFormat(str(pdf.resolve()), WD_EXPORT_PDF)
        return {"stories": story_text(doc), "pdf": str(pdf)}
    finally:
        doc.Close(False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("organic", type=Path)
    parser.add_argument("injected", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/word-gate"))
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("release_gate.py requires Windows and Microsoft Word")
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "release_gate.py requires pywin32: python -m pip install pywin32"
        ) from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    report = {"word_version": str(word.Version), "operations": {}}
    failures = []
    try:
        for operation in (
            "baseline", "renumber", "delete", "convert", "track-accept", "track-reject"
        ):
            organic = exercise(
                word, args.organic, args.output_dir / f"organic-{operation}.docx", operation
            )
            injected = exercise(
                word, args.injected, args.output_dir / f"injected-{operation}.docx", operation
            )
            equal = organic["stories"] == injected["stories"]
            report["operations"][operation] = {
                "visible_story_text_equal": equal,
                "organic": organic,
                "injected": injected,
            }
            if not equal:
                failures.append(operation)
    finally:
        word.Quit()
    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(report_path)
    if failures:
        raise SystemExit("Differential failures: " + ", ".join(failures))


if __name__ == "__main__":
    main()
