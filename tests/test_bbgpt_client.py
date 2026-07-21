import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "legal-bibliography"
    / "scripts"
    / "bbgpt_client.py"
)
SPEC = importlib.util.spec_from_file_location("bbgpt_client", SCRIPT)
bbgpt_client = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bbgpt_client)


class BbgptClientTests(unittest.TestCase):
    def test_fast_preset_is_deterministic(self):
        self.assertEqual(
            bbgpt_client.resolve_engines("fast"),
            "crossref,openalex,courtlistener",
        )

    def test_broad_preset_omits_optional_archive_engine(self):
        engines = bbgpt_client.resolve_engines("broad").split(",")
        self.assertIn("hollis", engines)
        self.assertIn("ssrn", engines)
        self.assertNotIn("annas", engines)

    def test_invalid_engine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            bbgpt_client.resolve_engines("crossref,not-a-source")


if __name__ == "__main__":
    unittest.main()
