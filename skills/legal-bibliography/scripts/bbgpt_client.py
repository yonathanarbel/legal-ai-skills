#!/usr/bin/env python3
"""Small standard-library client for BBGpt legal bibliography searches."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = os.environ.get("BBGPT_BASE_URL", "https://bbgpt.battleoftheforms.com")
ENGINE_PRESETS = {
    "fast": "crossref,openalex,courtlistener",
    "broad": "hollis,ssrn,crossref,openalex,courtlistener",
}
PUBLIC_ENGINES = frozenset({"hollis", "ssrn", "annas", "crossref", "openalex", "courtlistener"})


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json", "User-Agent": "legal-bibliography-skill/1.0"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"BBGpt HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"BBGpt request failed: {exc.reason}") from exc


def resolve_engines(value: str) -> str:
    resolved = ENGINE_PRESETS.get(value, value)
    engines = [engine.strip().lower() for engine in resolved.split(",") if engine.strip()]
    invalid = sorted(set(engines) - PUBLIC_ENGINES)
    if invalid:
        allowed = ", ".join(sorted(PUBLIC_ENGINES))
        raise ValueError(f"Unsupported BBGpt engine(s): {', '.join(invalid)}. Public engines: {allowed}")
    if not engines:
        raise ValueError("At least one BBGpt engine is required")
    return ",".join(dict.fromkeys(engines))


def search_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "q": args.query,
        "engines": resolve_engines(args.engines),
        "use_llm": not args.no_llm,
        "top_per_engine": args.top_per_engine,
        "timeout": args.timeout,
    }


def synchronous_search(args: argparse.Namespace) -> dict[str, Any]:
    query = urllib.parse.urlencode(search_payload(args))
    return request_json(
        f"{args.base_url}/api/search?{query}",
        timeout=args.timeout + 15,
    )


def job_search(args: argparse.Namespace) -> dict[str, Any]:
    submitted = request_json(
        f"{args.base_url}/api/search",
        method="POST",
        payload=search_payload(args),
        timeout=15,
    )
    job_id = submitted.get("job_id")
    if not job_id:
        raise RuntimeError(f"BBGpt did not return a job id: {submitted}")
    print(f"BBGpt job {job_id} submitted", file=sys.stderr)

    deadline = time.monotonic() + args.timeout + 30
    previous_status = None
    while time.monotonic() < deadline:
        job = request_json(
            f"{args.base_url}/api/search/jobs/{urllib.parse.quote(job_id)}",
            timeout=10,
        )
        status = job.get("status")
        if status != previous_status:
            print(f"BBGpt job {job_id}: {status}", file=sys.stderr)
            previous_status = status
        if status == "completed":
            result = job.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("BBGpt completed the job without a result object")
            return result
        if status == "failed":
            raise RuntimeError(f"BBGpt job failed: {job.get('error', 'unknown error')}")
        time.sleep(args.poll_interval)
    raise TimeoutError(f"BBGpt job {job_id} did not finish before the client deadline")


def emit(data: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
        print(f"Wrote {output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"BBGpt base URL (default: {DEFAULT_BASE_URL})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="Check BBGpt readiness")
    health.add_argument("--output")

    search = subparsers.add_parser("search", help="Run a structured bibliography search")
    search.add_argument("query")
    search.add_argument(
        "--engines",
        default="broad",
        help="fast, broad, or a comma-separated public engine list",
    )
    search.add_argument("--no-llm", action="store_true", help="Disable LLM ranking/enhancement")
    search.add_argument("--sync", action="store_true", help="Use synchronous GET instead of a job")
    search.add_argument("--top-per-engine", type=int, default=3)
    search.add_argument("--timeout", type=int, default=90)
    search.add_argument("--poll-interval", type=float, default=1.0)
    search.add_argument("--output")

    cite = subparsers.add_parser("cite", help="Format results from a BBGpt JSON response")
    cite.add_argument("input")
    cite.add_argument("--query", default="")
    cite.add_argument("--output")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.base_url = args.base_url.rstrip("/")
    try:
        if args.command == "health":
            result = request_json(f"{args.base_url}/health", timeout=15)
        elif args.command == "search":
            if not 1 <= args.top_per_engine <= 50:
                parser.error("--top-per-engine must be between 1 and 50")
            if not 10 <= args.timeout <= 300:
                parser.error("--timeout must be between 10 and 300")
            result = synchronous_search(args) if args.sync else job_search(args)
        else:
            source = json.loads(Path(args.input).read_text(encoding="utf-8"))
            results = source.get("results") if isinstance(source, dict) else source
            if not isinstance(results, list) or not results:
                raise ValueError("Input must be a result array or an object with a nonempty results array")
            source_query = source.get("query", "") if isinstance(source, dict) else ""
            result = request_json(
                f"{args.base_url}/api/citations",
                method="POST",
                payload={"query": args.query or source_query, "results": results},
                timeout=120,
            )
        emit(result, args.output)
        return 0
    except (RuntimeError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
