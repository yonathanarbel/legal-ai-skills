import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "lawreview-research"
    / "scripts"
    / "lawcorpus.py"
)
SPEC = importlib.util.spec_from_file_location("lawcorpus", SCRIPT)
lawcorpus = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lawcorpus)


class LawCorpusTests(unittest.TestCase):
    def test_diversify_documents_preserves_rank_order(self):
        rows = [
            {"document_key": "a", "rank": 1},
            {"document_key": "a", "rank": 2},
            {"document_key": "b", "rank": 3},
            {"document_key": "c", "rank": 4},
        ]
        self.assertEqual(
            [row["document_key"] for row in lawcorpus.diversify_documents(rows, 2)],
            ["a", "b"],
        )

    def test_connect_available_falls_back_when_live_db_is_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.sqlite"
            snapshot = Path(tmp) / "snapshot.sqlite"
            live_writer = sqlite3.connect(live)
            live_writer.execute("CREATE TABLE marker(value TEXT)")
            live_writer.commit()
            snapshot_writer = sqlite3.connect(snapshot)
            snapshot_writer.execute("CREATE TABLE marker(value TEXT)")
            snapshot_writer.commit()
            snapshot_writer.close()
            live_writer.execute("BEGIN EXCLUSIVE")
            try:
                conn, selected = lawcorpus.connect_available(live, snapshot, timeout=0.01)
                self.assertEqual(selected, snapshot)
                conn.close()
            finally:
                live_writer.rollback()
                live_writer.close()

    def test_connect_available_prefers_readable_live_db_over_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp) / "live.sqlite"
            snapshot = Path(tmp) / "snapshot.sqlite"
            for path, value in ((live, "live"), (snapshot, "snapshot")):
                writer = sqlite3.connect(path)
                writer.execute("CREATE TABLE marker(value TEXT)")
                writer.execute("INSERT INTO marker VALUES (?)", (value,))
                writer.commit()
                writer.close()
            Path(f"{snapshot}.json").write_text(json.dumps({"counts": {"documents": 1}}))

            conn, selected = lawcorpus.connect_available(live, snapshot, timeout=0.01)
            try:
                self.assertEqual(selected, live)
                self.assertEqual(conn.execute("SELECT value FROM marker").fetchone()[0], "live")
            finally:
                conn.close()

    def test_corpus_stats_uses_snapshot_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "snapshot.sqlite"
            writer = sqlite3.connect(db)
            writer.execute("CREATE TABLE marker(value TEXT)")
            writer.commit()
            writer.close()
            Path(f"{db}.json").write_text(
                json.dumps(
                    {
                        "counts": {"documents": 10, "pages": 100},
                        "document_char_total": 5000,
                        "journal_count": 3,
                        "max_document_updated_at": "now",
                    }
                )
            )
            conn = lawcorpus.connect_db(db)
            result = lawcorpus.corpus_stats(conn, db)
            conn.close()
            self.assertEqual(result["counts"]["documents"], 10)
            self.assertEqual(result["document_page_total"], 100)
            self.assertEqual(result["journal_count"], 3)

    def test_find_citing_exact_uses_a_complete_normalized_citation(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
          CREATE TABLE documents(document_key TEXT PRIMARY KEY,archive_remote_path TEXT,
            source_id INTEGER,journal_hint TEXT,member_path TEXT);
          CREATE TABLE metadata_guess(document_key TEXT,title_guess TEXT,authors_json TEXT,year_guess INTEGER);
          CREATE TABLE citations(citation_text TEXT,normalized_cite TEXT,parser TEXT,
            citation_type TEXT,page_number INTEGER,local_path TEXT,document_key TEXT);
          INSERT INTO documents VALUES ('exact','a',1,'journal','exact.pdf');
          INSERT INTO documents VALUES ('other','a',1,'journal','other.pdf');
          INSERT INTO citations VALUES ('15 U.S.C. § 1','15 U.S.C. § 1','regex','statute',1,'p','exact');
          INSERT INTO citations VALUES ('15 U.S.C. § 10','15 U.S.C. § 10','regex','statute',1,'p','other');
        """)
        rows = lawcorpus.find_citing(conn, "15 U.S.C. § 1", exact=True)
        self.assertEqual([row["document_key"] for row in rows], ["exact"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
