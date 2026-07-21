"""Empirically demonstrate body-vs-footnote-story field update coverage."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import win32com.client  # type: ignore[import-not-found]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument("--work", type=Path, default=Path("artifacts/update-probe.docx"))
    args = parser.parse_args()
    args.work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.docx, args.work)
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(args.work.resolve()), AddToRecentFiles=False)
        try:
            doc.Footnotes.Add(doc.Range(0, 0), Text="Probe note.")
            field = doc.StoryRanges(2).Fields(1)  # wdFootnotesStory
            before = field.Result.Text
            doc.Content.Fields.Update()
            after_body_update = field.Result.Text
            doc.StoryRanges(2).Fields.Update()
            after_footnote_update = field.Result.Text
            result = {
                "word_version": str(word.Version),
                "before": before,
                "after_body_story_update": after_body_update,
                "after_footnote_story_update": after_footnote_update,
            }
            print(json.dumps(result, indent=2))
            if after_body_update != before or after_footnote_update == before:
                raise SystemExit("Observed update semantics did not match the expected trap")
        finally:
            doc.Close(False)
    finally:
        word.Quit()


if __name__ == "__main__":
    main()
