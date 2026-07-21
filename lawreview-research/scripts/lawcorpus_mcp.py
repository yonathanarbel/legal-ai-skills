#!/usr/bin/env python3
"""Minimal stdio MCP server for the law review research database."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Any

import lawcorpus


TOOLS: list[dict[str, Any]] = [
    {
        "name": "corpus_stats",
        "description": "Return live corpus counts for the OCR-backed law review research database.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_journals",
        "description": "List journal hints currently represented in the OCR-backed law review corpus.",
        "inputSchema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 200, "minimum": 1}},
            "additionalProperties": False,
        },
    },
    {
        "name": "search",
        "description": "Search law review OCR text. Use mode='chunk' for research passages, 'page' for page OCR hits, and 'citation' for legal citation lookups.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {"type": "string", "enum": ["chunk", "page", "citation"], "default": "chunk"},
                "k": {"type": "integer", "default": 10, "minimum": 1},
                "journal": {"type": "string"},
                "unique_documents": {"type": "boolean", "default": True},
                "after": {"type": "integer"},
                "before": {"type": "integer"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_document",
        "description": "Fetch one document by document_key, source_id, or member_path substring, with OCR page text up to max_chars.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_key": {"type": "string"},
                "source_id": {"type": "integer"},
                "member_like": {"type": "string"},
                "max_chars": {"type": "integer", "default": 20000, "minimum": 0},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_context",
        "description": "Expand around a chunk hit by chunk_id, or by document_key plus chunk_index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chunk_id": {"type": "integer"},
                "document_key": {"type": "string"},
                "chunk_index": {"type": "integer"},
                "before": {"type": "integer", "default": 2, "minimum": 0},
                "after": {"type": "integer", "default": 2, "minimum": 0},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "find_citing",
        "description": "Find documents/pages containing a citation string, such as '15 U.S.C. § 1' or '410 U.S. 113'.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "citation": {"type": "string"},
                "k": {"type": "integer", "default": 25, "minimum": 1},
                "journal": {"type": "string"},
                "unique_documents": {"type": "boolean", "default": True},
            },
            "required": ["citation"],
            "additionalProperties": False,
        },
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Law corpus MCP server over stdio")
    parser.add_argument("--db", default=lawcorpus.DEFAULT_DB)
    parser.add_argument("--snapshot-fallback", default=lawcorpus.DEFAULT_SNAPSHOT)
    return parser.parse_args()


def result_text(payload: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ],
        "isError": False,
    }


def error_text(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def call_tool(conn, name: str, args: dict[str, Any], db_path: str) -> dict[str, Any]:
    if name == "corpus_stats":
        return result_text(lawcorpus.corpus_stats(conn, db_path))
    if name == "list_journals":
        return result_text(lawcorpus.list_journals(conn, int(args.get("limit", 200))))
    if name == "search":
        mode = args.get("mode", "chunk")
        query = args["query"]
        k = int(args.get("k", 10))
        journal = args.get("journal")
        after = args.get("after")
        before = args.get("before")
        unique_documents = bool(args.get("unique_documents", True))
        if mode == "page":
            payload = lawcorpus.search_pages(conn, query, k, journal, after, before, unique_documents)
        elif mode == "citation":
            payload = lawcorpus.find_citing(conn, query, k, journal, unique_documents)
        else:
            payload = lawcorpus.search_chunks(conn, query, k, journal, after, before, unique_documents)
        return result_text(payload)
    if name == "get_document":
        return result_text(
            lawcorpus.get_document(
                conn,
                args.get("document_key"),
                args.get("source_id"),
                args.get("member_like"),
                int(args.get("max_chars", 20000)),
            )
        )
    if name == "get_context":
        return result_text(
            lawcorpus.get_context(
                conn,
                args.get("chunk_id"),
                args.get("document_key"),
                args.get("chunk_index"),
                int(args.get("before", 2)),
                int(args.get("after", 2)),
            )
        )
    if name == "find_citing":
        return result_text(
            lawcorpus.find_citing(
                conn,
                args["citation"],
                int(args.get("k", 25)),
                args.get("journal"),
                bool(args.get("unique_documents", True)),
            )
        )
    return error_text(f"unknown tool: {name}")


def send(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    args = parse_args()
    try:
        conn, active_db = lawcorpus.connect_available(args.db, args.snapshot_fallback)
    except Exception as exc:
        print(f"lawcorpus_mcp: {exc}", file=sys.stderr)
        return 2

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            method = msg.get("method")
            msg_id = msg.get("id")
            if method == "notifications/initialized":
                continue
            if method == "initialize":
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "lawcorpus", "version": "0.1.0"},
                        },
                    }
                )
            elif method == "tools/list":
                send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
            elif method == "tools/call":
                params = msg.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments") or {}
                try:
                    payload = call_tool(conn, tool_name, tool_args, str(active_db))
                except sqlite3.OperationalError as exc:
                    fallback = Path(args.snapshot_fallback) if args.snapshot_fallback else None
                    if (
                        "locked" not in str(exc).lower()
                        or fallback is None
                        or Path(active_db) == fallback
                    ):
                        raise
                    conn.close()
                    conn, active_db = lawcorpus.connect_available(
                        fallback, snapshot_fallback=None
                    )
                    payload = call_tool(conn, tool_name, tool_args, str(active_db))
                send({"jsonrpc": "2.0", "id": msg_id, "result": payload})
            elif msg_id is not None:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"method not found: {method}"},
                    }
                )
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            if "msg" in locals() and isinstance(msg, dict) and msg.get("id") is not None:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "result": error_text(str(exc)),
                    }
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
