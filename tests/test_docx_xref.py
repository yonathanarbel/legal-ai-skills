import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / "inject-word-cross-references" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from docx_xref.injector import CrossReferenceInjector  # noqa: E402
from docx_xref.models import (  # noqa: E402
    CrossReferenceRequest,
    FootnoteTarget,
    MarkerPlacement,
    ReferenceKind,
)
from docx_xref.package import DocxPackage  # noqa: E402
from docx_xref.validator import validate_package  # noqa: E402


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def write_synthetic_docx(path: Path) -> None:
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}"><w:body>
  <w:p><w:r><w:rPr><w:i/></w:rPr><w:footnoteReference w:id="5"/></w:r></w:p>
  <w:p><w:r><w:footnoteReference w:id="9"/></w:r></w:p>
  <w:sectPr/>
</w:body></w:document>""".encode()
    footnotes = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="{W}">
  <w:footnote w:type="separator" w:id="-1"><w:p/></w:footnote>
  <w:footnote w:id="5"><w:p><w:r><w:footnoteRef/></w:r><w:r><w:t>First authority.</w:t></w:r></w:p></w:footnote>
  <w:footnote w:id="9"><w:p><w:r><w:footnoteRef/></w:r><w:r><w:rPr><w:i/></w:rPr><w:t>See supra note [[XREF:AUTH]].</w:t></w:r></w:p></w:footnote>
</w:footnotes>""".encode()
    content_types = b"<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("word/document.xml", document)
        docx.writestr("word/footnotes.xml", footnotes)


class DocxCrossReferenceTests(unittest.TestCase):
    def test_injects_noteref_and_preserves_untouched_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.docx"
            output = Path(tmp) / "output.docx"
            manifest = Path(tmp) / "manifest.json"
            write_synthetic_docx(source)
            with zipfile.ZipFile(source) as package:
                original_content_types = package.read("[Content_Types].xml")

            request = CrossReferenceRequest(
                target=FootnoteTarget(5),
                placement=MarkerPlacement(
                    part="word/footnotes.xml",
                    footnote_id=9,
                    marker="[[XREF:AUTH]]",
                ),
                kind=ReferenceKind.FOOTNOTE_NUMBER,
                hyperlink=True,
            )
            entries = CrossReferenceInjector().inject(source, output, [request], manifest)

            self.assertEqual(entries[0].computed_cache, "1")
            report = validate_package(DocxPackage(output))
            self.assertTrue(report.ok, report.errors)
            with zipfile.ZipFile(output) as package:
                self.assertEqual(package.read("[Content_Types].xml"), original_content_types)
                self.assertIn(b"NOTEREF", package.read("word/footnotes.xml"))
                self.assertIn(b"bookmarkStart", package.read("word/document.xml"))
            payload = json.loads(manifest.read_text())
            self.assertEqual(payload["references"][0]["computed_cache"], "1")


if __name__ == "__main__":
    unittest.main()
