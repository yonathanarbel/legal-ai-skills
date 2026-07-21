---
name: lawreview-research
description: Search and inspect an authorized OCR-backed law-review corpus stored in a compatible SQLite database. Use for passage retrieval, citation lookup, context expansion, document inspection, journal filtering, corpus statistics, and retrieval evaluation with the bundled lawcorpus CLI or MCP server. Treat OCR text and inferred metadata as provisional, and never assume the corpus is complete or current.
---

# Law Review Research

Use the bundled read-only CLI to search a compatible SQLite/FTS corpus. The skill does not include article text or a database; the user must supply material they are authorized to process.

## Non-negotiable rules

- Treat OCR, title guesses, author guesses, journal hints, and year guesses as provisional.
- Expand context before relying on a search hit, then verify important language against an authoritative copy.
- Report corpus scope, filters, query mode, and known gaps. Do not describe silence in the corpus as absence in the literature.
- Quote only as much text as the user's rights and applicable law permit.
- Open databases read-only. Do not modify, rebuild, or redistribute a corpus unless the user explicitly authorizes it and has the necessary rights.
- Do not expose local paths, document identifiers, or corpus contents that the user has not authorized for disclosure.

## Configure

Set the database path before running the tools:

```bash
export LAWCORPUS_DB=/path/to/lawreview_search.sqlite
```

Optionally configure a consistent snapshot used when the primary database is locked:

```bash
export LAWCORPUS_SNAPSHOT=/path/to/lawreview_search.latest.sqlite
```

Command-line `--db` and `--snapshot-fallback` values override the environment. Read [references/schema.md](references/schema.md) when creating or diagnosing a compatible database.

## Workflow

1. Run `stats` to understand the indexed corpus.
2. Use chunk search for normal research questions and passage retrieval.
3. Use `context` around promising chunks.
4. Use page search when the page location matters or chunking missed a phrase.
5. Use `citing` or citation mode for legal citation strings.
6. Fetch a document only when larger OCR context is necessary.
7. Verify important results against authoritative copies and report search limitations.

Run from this skill directory:

```bash
python scripts/lawcorpus.py stats
python scripts/lawcorpus.py search --mode chunk --limit 10 \
  '"reasonable person" objective negligence'
python scripts/lawcorpus.py context --chunk-id 9795 --before 2 --after 2
python scripts/lawcorpus.py citing '15 U.S.C. § 1' --limit 25
```

Useful options:

```text
search --mode chunk|page|citation
       --limit N
       --journal TEXT
       --after YEAR
       --before YEAR
       --allow-duplicate-documents

document --document-key KEY | --source-id ID | --member-like TEXT
         --max-chars N

context  --chunk-id ID
         --before N --after N
```

Chunk and page search return at most one hit per document by default. Allow duplicates only when exhaustive within-document retrieval matters more than breadth.

SQLite FTS5 syntax applies. Prefer direct legal terms and quoted phrases. If punctuation causes an FTS error, simplify the query; use `citing` for citation strings containing symbols such as `§`.

## Evaluate retrieval

Use a JSONL gold set:

```json
{"id":"privacy-1","query":"privacy tort appropriation likeness","mode":"chunk","expected_title_contains":["privacy"]}
{"id":"antitrust-1","query":"15 U.S.C. § 1","mode":"citation","expected_citation_contains":["15 U.S.C."]}
```

Run:

```bash
python scripts/evaluate_search.py queries.jsonl
```

Report recall@k and mean reciprocal rank before claiming a retrieval change improved results.

## Optional MCP server

The bundled dependency-free JSON-RPC stdio server exposes the same read-only primitives:

```bash
python scripts/lawcorpus_mcp.py --db "$LAWCORPUS_DB"
```

Tools: `corpus_stats`, `list_journals`, `search`, `get_document`, `get_context`, and `find_citing`. Prefer the CLI for shell-based agents and MCP only when the runtime is configured to launch local stdio servers.

## Deliver results

For each important hit, provide the provisional title/author/year when present, journal hint, passage or citation match, page/chunk location, and verification status. End with a compact coverage note identifying the query, mode, filters, corpus date or snapshot, and material limitations.
