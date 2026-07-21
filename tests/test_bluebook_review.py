import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "bluebook-review"
    / "scripts"
    / "fetch_epps_bluebook.py"
)
SPEC = importlib.util.spec_from_file_location("fetch_epps_bluebook", SCRIPT)
fetcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(fetcher)

INSPECTOR_SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "bluebook-review"
    / "scripts"
    / "inspect_docx_citations.py"
)
INSPECTOR_SPEC = importlib.util.spec_from_file_location("inspect_docx_citations", INSPECTOR_SCRIPT)
inspector = importlib.util.module_from_spec(INSPECTOR_SPEC)
assert INSPECTOR_SPEC.loader is not None
INSPECTOR_SPEC.loader.exec_module(inspector)


class BluebookReviewTests(unittest.TestCase):
    def test_fetches_commit_pinned_bundle_and_validates_offline(self):
        commit = "a" * 40
        payloads = {
            "README.md": b"# Epps guide\n",
            "BluebookDSEStyle.csl": b"<style/>",
            "LICENSE": b"CC BY-SA 4.0\n",
        }

        def fake_request(url, timeout=30):
            del timeout
            for name, payload in payloads.items():
                if url.endswith("/" + name):
                    return payload
            raise AssertionError(f"unexpected URL: {url}")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with mock.patch.object(fetcher, "resolve_commit", return_value=commit), mock.patch.object(
                fetcher, "request_bytes", side_effect=fake_request
            ):
                metadata = fetcher.fetch_bundle(output, "main")

            self.assertEqual(metadata["resolved_commit"], commit)
            self.assertEqual(metadata["license"], "CC-BY-SA-4.0")
            self.assertIn(f"/{commit}/README.md", metadata["files"]["README.md"]["url"])
            self.assertEqual(fetcher.validate_offline(output)["resolved_commit"], commit)

            (output / "README.md").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                fetcher.validate_offline(output)

    def test_inspects_note_order_and_zotero_fields(self):
        namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        document = f"""<w:document xmlns:w="{namespace}"><w:body><w:p><w:r>
          <w:footnoteReference w:id="5"/>
        </w:r></w:p></w:body></w:document>"""
        footnotes = f"""<w:footnotes xmlns:w="{namespace}">
          <w:footnote w:type="separator" w:id="-1"><w:p/></w:footnote>
          <w:footnote w:id="5"><w:p>
            <w:fldSimple w:instr=" ADDIN ZOTERO_ITEM CSL_CITATION test ">
              <w:r><w:t>Brown v. Board of Education, 347 U.S. 483 (1954)</w:t></w:r>
            </w:fldSimple>
          </w:p></w:footnote>
        </w:footnotes>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("word/document.xml", document)
                package.writestr("word/footnotes.xml", footnotes)

            payload = inspector.inspect_docx(path)
            self.assertEqual(len(payload["notes"]), 1)
            note = payload["notes"][0]
            self.assertEqual(note["reference_order"], 1)
            self.assertTrue(note["has_zotero_field"])
            self.assertTrue(note["paragraphs"][0]["citation_hint"])


if __name__ == "__main__":
    unittest.main()
