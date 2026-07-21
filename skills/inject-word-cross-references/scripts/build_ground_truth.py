"""Create the organic corpus through Microsoft Word's object model.

The checked-in VBA module is canonical. This driver mirrors it so a release
workstation can generate the corpus without lowering macro-security settings.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WD_COLLAPSE_END = 0
WD_FORMAT_XML_DOCUMENT = 12
WD_REF_TYPE_FOOTNOTE = 3
CASES = {
    "noteref": (5, False),          # wdFootnoteNumber
    "noteref_h": (5, True),
    "noteref_f": (16, False),      # wdFootnoteNumberFormatted
    "noteref_f_h": (16, True),
    "noteref_p": (15, False),      # wdPosition; Word persists this as REF
    "noteref_p_h": (15, True),
}


def build(output_dir: Path) -> list[Path]:
    import win32com.client  # type: ignore[import-not-found]

    output_dir.mkdir(parents=True, exist_ok=True)
    destinations: list[Path] = []
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    version = str(word.Version)
    try:
        for stem, (reference_kind, hyperlink) in CASES.items():
            destination = (output_dir / f"{stem}.docx").resolve()
            doc = word.Documents.Add()
            try:
                doc.Content.Text = "Alpha target sentence.\rBeta referring sentence.\r"
                target = doc.Paragraphs(1).Range.Duplicate
                target.MoveEnd(1, -1)
                target.Collapse(WD_COLLAPSE_END)
                doc.Footnotes.Add(target, Text="Target note text.")

                referring = doc.Paragraphs(2).Range.Duplicate
                referring.MoveEnd(1, -1)
                referring.Collapse(WD_COLLAPSE_END)
                doc.Footnotes.Add(referring, Text="Referring note. See supra note ")

                insertion = doc.Footnotes(2).Range.Duplicate
                insertion.MoveEnd(1, -1)
                insertion.Collapse(WD_COLLAPSE_END)
                insertion.InsertCrossReference(
                    ReferenceType=WD_REF_TYPE_FOOTNOTE,
                    ReferenceKind=reference_kind,
                    ReferenceItem=1,
                    InsertAsHyperlink=hyperlink,
                    IncludePosition=False,
                    SeparateNumbers=False,
                    SeparatorString=" ",
                )
                doc.SaveAs2(str(destination), WD_FORMAT_XML_DOCUMENT, AddToRecentFiles=False)
                destinations.append(destination)
            finally:
                doc.Close(False)
        destination = (output_dir / "ref_bookmark_h.docx").resolve()
        doc = word.Documents.Add()
        try:
            doc.Content.Text = "Target phrase.\rSee target: \r"
            bookmark_range = doc.Paragraphs(1).Range.Duplicate
            bookmark_range.MoveEnd(1, -1)
            doc.Bookmarks.Add("UserTarget", bookmark_range)
            insertion = doc.Paragraphs(2).Range.Duplicate
            insertion.MoveEnd(1, -1)
            insertion.Collapse(WD_COLLAPSE_END)
            insertion.InsertCrossReference(
                ReferenceType=2, ReferenceKind=-1, ReferenceItem="UserTarget",
                InsertAsHyperlink=True, IncludePosition=False,
            )
            doc.SaveAs2(str(destination), WD_FORMAT_XML_DOCUMENT, AddToRecentFiles=False)
            destinations.append(destination)
        finally:
            doc.Close(False)

        destination = (output_dir / "ref_heading_h.docx").resolve()
        doc = word.Documents.Add()
        try:
            doc.Content.Text = "Target heading\rSee heading: \r"
            doc.Paragraphs(1).Style = "Heading 1"
            insertion = doc.Paragraphs(2).Range.Duplicate
            insertion.MoveEnd(1, -1)
            insertion.Collapse(WD_COLLAPSE_END)
            insertion.InsertCrossReference(
                ReferenceType=1, ReferenceKind=-1, ReferenceItem=1,
                InsertAsHyperlink=True, IncludePosition=False,
            )
            doc.SaveAs2(str(destination), WD_FORMAT_XML_DOCUMENT, AddToRecentFiles=False)
            destinations.append(destination)
        finally:
            doc.Close(False)
    finally:
        word.Quit()

    (output_dir / "generation.json").write_text(
        json.dumps({"word_version": version, "documents": [p.name for p in destinations]}, indent=2),
        encoding="utf-8",
    )
    return destinations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("corpus/organic"))
    args = parser.parse_args()
    for path in build(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
