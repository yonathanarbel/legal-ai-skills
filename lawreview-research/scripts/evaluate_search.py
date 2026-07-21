#!/usr/bin/env python3
"""Evaluate live law corpus search against a small JSONL gold set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import lawcorpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate law corpus search")
    parser.add_argument("queries_jsonl", help="JSONL records with query, expected docs, and optional mode/k")
    parser.add_argument("--db", default=lawcorpus.DEFAULT_DB)
    parser.add_argument("--default-mode", choices=["chunk", "page", "citation"], default="chunk")
    parser.add_argument("--default-k", type=int, default=10)
    return parser.parse_args()


def load_queries(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if "query" not in record:
                raise ValueError(f"{path}:{line_no}: missing query")
            records.append(record)
    return records


def run_query(conn, record: dict[str, Any], default_mode: str, default_k: int) -> list[dict[str, Any]]:
    query = record["query"]
    mode = record.get("mode", default_mode)
    k = int(record.get("k", default_k))
    journal = record.get("journal")
    after = record.get("after")
    before = record.get("before")
    if mode == "page":
        return lawcorpus.search_pages(conn, query, k, journal, after, before)
    if mode == "citation":
        return lawcorpus.find_citing(conn, query, k, journal)
    return lawcorpus.search_chunks(conn, query, k, journal, after, before)


def is_relevant(row: dict[str, Any], record: dict[str, Any]) -> bool:
    expected_keys = set(record.get("expected_document_keys") or [])
    if expected_keys and row.get("document_key") in expected_keys:
        return True
    member_needles = [str(v).lower() for v in record.get("expected_member_contains") or []]
    member_path = str(row.get("member_path") or "").lower()
    if any(needle in member_path for needle in member_needles):
        return True
    title_needles = [str(v).lower() for v in record.get("expected_title_contains") or []]
    title = str(row.get("title_guess") or "").lower()
    if any(needle in title for needle in title_needles):
        return True
    citation_needles = [str(v).lower() for v in record.get("expected_citation_contains") or []]
    citation = str(row.get("citation_text") or row.get("snippet") or "").lower()
    return any(needle in citation for needle in citation_needles)


def reciprocal_rank(rows: list[dict[str, Any]], record: dict[str, Any]) -> float:
    for idx, row in enumerate(rows, start=1):
        if is_relevant(row, record):
            return 1.0 / idx
    return 0.0


def main() -> int:
    args = parse_args()
    records = load_queries(Path(args.queries_jsonl))
    conn = lawcorpus.connect_db(args.db)
    results = []
    hits = 0
    rr_total = 0.0
    for record in records:
        rows = run_query(conn, record, args.default_mode, args.default_k)
        hit = any(is_relevant(row, record) for row in rows)
        rr = reciprocal_rank(rows, record)
        hits += int(hit)
        rr_total += rr
        results.append(
            {
                "id": record.get("id"),
                "query": record["query"],
                "mode": record.get("mode", args.default_mode),
                "k": int(record.get("k", args.default_k)),
                "hit": hit,
                "reciprocal_rank": rr,
                "top_document_keys": [row.get("document_key") for row in rows[:5]],
                "top_member_paths": [row.get("member_path") for row in rows[:5]],
            }
        )
    n = len(records)
    payload = {
        "query_count": n,
        "recall_at_k": hits / n if n else None,
        "mrr": rr_total / n if n else None,
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
