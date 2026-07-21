#!/usr/bin/env python3
"""Agent-facing CLI for the live law review research database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


DEFAULT_DB = os.environ.get("LAWCORPUS_DB", "lawreview_search.sqlite")
DEFAULT_SNAPSHOT = os.environ.get("LAWCORPUS_SNAPSHOT")


def connect_db(db_path: str | Path, timeout: float = 1) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"missing database: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={max(1, int(timeout * 1000))}")
    return conn


def connect_available(
    db_path: str | Path,
    snapshot_fallback: str | Path | None = DEFAULT_SNAPSHOT,
    timeout: float = 1,
) -> tuple[sqlite3.Connection, Path]:
    candidates = [Path(db_path)]
    if snapshot_fallback:
        fallback = Path(snapshot_fallback)
        if fallback != candidates[0]:
            candidates.append(fallback)
    errors = []
    for candidate in candidates:
        conn = None
        try:
            conn = connect_db(candidate, timeout=timeout)
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return conn, candidate
        except (OSError, sqlite3.Error) as exc:
            errors.append(f"{candidate}: {exc}")
            if conn is not None:
                conn.close()
    raise RuntimeError("no readable corpus database; " + "; ".join(errors))


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def diversify_documents(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    diversified = []
    for row in rows:
        document_key = str(row.get("document_key") or "")
        if document_key and document_key in seen:
            continue
        if document_key:
            seen.add(document_key)
        diversified.append(row)
        if len(diversified) >= limit:
            break
    return diversified


def table_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise
        return None
    except sqlite3.Error:
        return None


def corpus_stats(conn: sqlite3.Connection, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    metadata_path = Path(f"{db_path}.json")
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            metadata = {}
        if metadata.get("counts"):
            counts = metadata["counts"]
            return {
                "db": str(db_path),
                "counts": counts,
                "document_page_total": metadata.get("document_page_total", counts.get("pages")),
                "document_char_total": metadata.get("document_char_total"),
                "journal_count": metadata.get("journal_count"),
                "max_document_updated_at": metadata.get("max_document_updated_at"),
                "snapshot_created_at": metadata.get("snapshot_created_at"),
            }
    counts = {
        table: table_count(conn, table)
        for table in ["documents", "pages", "metadata_guess", "chunks", "chunk_fts", "citations"]
    }
    row = conn.execute(
        """
        SELECT
            max(updated_at) AS max_document_updated_at,
            sum(page_count) AS document_page_total,
            sum(char_count) AS document_char_total,
            count(DISTINCT journal_hint) AS journal_count
        FROM documents
        """
    ).fetchone()
    return {
        "db": str(db_path),
        "counts": counts,
        "document_page_total": row["document_page_total"],
        "document_char_total": row["document_char_total"],
        "journal_count": row["journal_count"],
        "max_document_updated_at": row["max_document_updated_at"],
    }


def list_journals(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            coalesce(journal_hint, 'unknown') AS journal,
            count(*) AS documents,
            sum(page_count) AS pages,
            sum(char_count) AS chars
        FROM documents
        GROUP BY coalesce(journal_hint, 'unknown')
        ORDER BY documents DESC, journal
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return rows_to_dicts(rows)


def _add_common_filters(
    sql: str,
    params: list[Any],
    journal: str | None,
    after: int | None,
    before: int | None,
    table_alias: str,
) -> tuple[str, list[Any]]:
    if journal:
        sql += f" AND {table_alias}.journal_hint LIKE ?"
        params.append(f"%{journal}%")
    if after is not None:
        sql += " AND (mg.year_guess IS NULL OR mg.year_guess >= ?)"
        params.append(after)
    if before is not None:
        sql += " AND (mg.year_guess IS NULL OR mg.year_guess <= ?)"
        params.append(before)
    return sql, params


def search_pages(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    journal: str | None = None,
    after: int | None = None,
    before: int | None = None,
    unique_documents: bool = True,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            page_fts.rank AS rank,
            snippet(page_fts, 0, '[', ']', ' ... ', 42) AS snippet,
            p.page_number,
            p.local_path,
            p.archive_remote_path,
            d.source_id,
            d.journal_hint,
            d.member_path,
            d.document_key,
            mg.title_guess,
            mg.authors_json,
            mg.year_guess
        FROM page_fts
        JOIN pages p ON p.id = page_fts.rowid
        JOIN documents d ON d.document_key = p.document_key
        LEFT JOIN metadata_guess mg ON mg.document_key = d.document_key
        WHERE page_fts MATCH ?
    """
    params: list[Any] = [query]
    sql, params = _add_common_filters(sql, params, journal, after, before, "d")
    sql += " ORDER BY page_fts.rank LIMIT ?"
    params.append(limit * 5 if unique_documents else limit)
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    return diversify_documents(rows, limit) if unique_documents else rows


def search_chunks(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    journal: str | None = None,
    after: int | None = None,
    before: int | None = None,
    unique_documents: bool = True,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            c.id AS chunk_id,
            chunk_fts.rank AS rank,
            snippet(chunk_fts, 1, '[', ']', ' ... ', 42) AS snippet,
            c.page_start,
            c.page_end,
            c.archive_remote_path,
            c.source_id,
            c.journal_hint,
            c.member_path,
            c.document_key,
            c.chunk_index,
            c.context_header,
            mg.title_guess,
            mg.authors_json,
            mg.year_guess
        FROM chunk_fts
        JOIN chunks c ON c.id = chunk_fts.rowid
        LEFT JOIN metadata_guess mg ON mg.document_key = c.document_key
        WHERE chunk_fts MATCH ?
    """
    params = [query]
    sql, params = _add_common_filters(sql, params, journal, after, before, "c")
    sql += " ORDER BY chunk_fts.rank LIMIT ?"
    params.append(limit * 5 if unique_documents else limit)
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    return diversify_documents(rows, limit) if unique_documents else rows


def find_citing(
    conn: sqlite3.Connection,
    citation: str,
    limit: int = 25,
    journal: str | None = None,
    unique_documents: bool = True,
    exact: bool = False,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            c.citation_text,
            c.normalized_cite,
            c.parser,
            c.citation_type,
            c.page_number,
            c.local_path,
            d.archive_remote_path,
            d.source_id,
            d.journal_hint,
            d.member_path,
            d.document_key,
            mg.title_guess,
            mg.authors_json,
            mg.year_guess
        FROM citations c
        JOIN documents d ON d.document_key = c.document_key
        LEFT JOIN metadata_guess mg ON mg.document_key = d.document_key
        WHERE (c.citation_text {operator} ? OR c.normalized_cite {operator} ?)
    """
    operator = "=" if exact else "LIKE"
    sql = sql.format(operator=operator)
    value = citation if exact else f"%{citation}%"
    params: list[Any] = [value, value]
    if journal:
        sql += " AND d.journal_hint LIKE ?"
        params.append(f"%{journal}%")
    sql += " ORDER BY CASE WHEN lower(c.normalized_cite)=lower(?) THEN 0 ELSE 1 END, c.citation_text, d.journal_hint, c.page_number LIMIT ?"
    params.append(citation)
    params.append(limit * 5 if unique_documents else limit)
    rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    return diversify_documents(rows, limit) if unique_documents else rows


def get_document(
    conn: sqlite3.Connection,
    document_key: str | None = None,
    source_id: int | None = None,
    member_like: str | None = None,
    max_chars: int = 20000,
) -> dict[str, Any]:
    sql = """
        SELECT d.*, mg.title_guess, mg.authors_json, mg.year_guess, mg.confidence AS metadata_confidence
        FROM documents d
        LEFT JOIN metadata_guess mg ON mg.document_key = d.document_key
        WHERE 1=1
    """
    params: list[Any] = []
    if document_key:
        sql += " AND d.document_key = ?"
        params.append(document_key)
    if source_id is not None:
        sql += " AND d.source_id = ?"
        params.append(source_id)
    if member_like:
        sql += " AND d.member_path LIKE ?"
        params.append(f"%{member_like}%")
    sql += " ORDER BY d.updated_at DESC LIMIT 1"
    doc = conn.execute(sql, params).fetchone()
    if doc is None:
        raise LookupError("document not found")

    pages = conn.execute(
        """
        SELECT page_key, page_number, local_path, chars, text
        FROM pages
        WHERE document_key=?
        ORDER BY page_number, inner_path
        """,
        (doc["document_key"],),
    ).fetchall()
    collected: list[dict[str, Any]] = []
    remaining = max_chars
    for page in pages:
        text = page["text"] or ""
        if remaining <= 0:
            collected.append(
                {
                    "page_key": page["page_key"],
                    "page_number": page["page_number"],
                    "local_path": page["local_path"],
                    "chars": page["chars"],
                    "text": None,
                    "truncated": True,
                }
            )
            continue
        page_text = text[:remaining]
        remaining -= len(page_text)
        collected.append(
            {
                "page_key": page["page_key"],
                "page_number": page["page_number"],
                "local_path": page["local_path"],
                "chars": page["chars"],
                "text": page_text,
                "truncated": len(page_text) < len(text),
            }
        )
    return {"document": dict(doc), "pages": collected, "page_count_returned": len(collected)}


def get_context(
    conn: sqlite3.Connection,
    chunk_id: int | None = None,
    document_key: str | None = None,
    chunk_index: int | None = None,
    before: int = 2,
    after: int = 2,
) -> dict[str, Any]:
    if chunk_id is not None:
        anchor = conn.execute("SELECT document_key, chunk_index FROM chunks WHERE id=?", (chunk_id,)).fetchone()
    elif document_key is not None and chunk_index is not None:
        anchor = {"document_key": document_key, "chunk_index": chunk_index}
    else:
        raise ValueError("provide chunk_id, or document_key plus chunk_index")
    if anchor is None:
        raise LookupError("chunk not found")

    start = int(anchor["chunk_index"]) - max(0, before)
    end = int(anchor["chunk_index"]) + max(0, after)
    rows = conn.execute(
        """
        SELECT id AS chunk_id, chunk_index, page_start, page_end, context_header, text
        FROM chunks
        WHERE document_key=? AND chunk_index BETWEEN ? AND ?
        ORDER BY chunk_index
        """,
        (anchor["document_key"], start, end),
    ).fetchall()
    doc = conn.execute(
        """
        SELECT d.document_key, d.source_id, d.archive_remote_path, d.journal_hint, d.member_path,
               mg.title_guess, mg.authors_json, mg.year_guess
        FROM documents d
        LEFT JOIN metadata_guess mg ON mg.document_key = d.document_key
        WHERE d.document_key=?
        """,
        (anchor["document_key"],),
    ).fetchone()
    return {"document": dict(doc) if doc else None, "chunks": rows_to_dicts(rows)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and inspect the law review corpus DB")
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="SQLite corpus path (default: LAWCORPUS_DB or ./lawreview_search.sqlite)",
    )
    parser.add_argument(
        "--snapshot-fallback",
        default=DEFAULT_SNAPSHOT,
        help="Optional fallback path (default: LAWCORPUS_SNAPSHOT)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    stats = sub.add_parser("stats")
    stats.set_defaults(func=cmd_stats)

    journals = sub.add_parser("journals")
    journals.add_argument("--limit", type=int, default=200)
    journals.set_defaults(func=cmd_journals)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=["page", "chunk", "citation"], default="chunk")
    search.add_argument("--limit", "-k", type=int, default=10)
    search.add_argument("--journal")
    search.add_argument("--after", type=int)
    search.add_argument("--before", type=int)
    search.add_argument(
        "--allow-duplicate-documents",
        action="store_true",
        help="Allow several matching pages/chunks from the same document in top results",
    )
    search.set_defaults(func=cmd_search)

    document = sub.add_parser("document")
    document.add_argument("--document-key")
    document.add_argument("--source-id", type=int)
    document.add_argument("--member-like")
    document.add_argument("--max-chars", type=int, default=20000)
    document.set_defaults(func=cmd_document)

    context = sub.add_parser("context")
    context.add_argument("--chunk-id", type=int)
    context.add_argument("--document-key")
    context.add_argument("--chunk-index", type=int)
    context.add_argument("--before", type=int, default=2)
    context.add_argument("--after", type=int, default=2)
    context.set_defaults(func=cmd_context)

    citing = sub.add_parser("citing")
    citing.add_argument("citation")
    citing.add_argument("--limit", "-k", type=int, default=25)
    citing.add_argument("--journal")
    citing.add_argument("--allow-duplicate-documents", action="store_true")
    citing.set_defaults(func=cmd_citing)
    return parser.parse_args()


def dump_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_stats(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    dump_json(corpus_stats(conn, args.active_db))


def cmd_journals(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    dump_json(list_journals(conn, args.limit))


def cmd_search(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    unique_documents = not args.allow_duplicate_documents
    if args.mode == "page":
        rows = search_pages(
            conn, args.query, args.limit, args.journal, args.after, args.before, unique_documents
        )
    elif args.mode == "citation":
        rows = find_citing(conn, args.query, args.limit, args.journal, unique_documents)
    else:
        rows = search_chunks(
            conn, args.query, args.limit, args.journal, args.after, args.before, unique_documents
        )
    dump_json(rows)


def cmd_document(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    dump_json(get_document(conn, args.document_key, args.source_id, args.member_like, args.max_chars))


def cmd_context(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    dump_json(get_context(conn, args.chunk_id, args.document_key, args.chunk_index, args.before, args.after))


def cmd_citing(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    dump_json(
        find_citing(
            conn,
            args.citation,
            args.limit,
            args.journal,
            not args.allow_duplicate_documents,
        )
    )


def main() -> int:
    args = parse_args()
    conn = None
    try:
        preferred_db = args.db
        preferred_fallback = args.snapshot_fallback
        conn, active_db = connect_available(preferred_db, preferred_fallback)
        args.active_db = str(active_db)
        try:
            args.func(conn, args)
        except sqlite3.OperationalError as exc:
            fallback = Path(args.snapshot_fallback) if args.snapshot_fallback else None
            if (
                "locked" not in str(exc).lower()
                or fallback is None
                or Path(active_db) == fallback
            ):
                raise
            conn.close()
            conn, active_db = connect_available(fallback, snapshot_fallback=None)
            args.active_db = str(active_db)
            args.func(conn, args)
        return 0
    except Exception as exc:
        print(f"lawcorpus: {exc}", file=sys.stderr)
        return 2
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
