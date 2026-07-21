---
name: legal-bibliography
description: Research, rank, verify, and format authoritative legal sources with the BBGpt bibliography service. Use for legal literature reviews, source collection, Bluebook-ready bibliographies, law review articles, treatises, books, working papers, cases, DOI and publication-metadata checks, citation cleanup, or finding the leading authorities on a legal doctrine. Do not treat search or LLM rankings as legal advice or as a substitute for checking the cited authority.
---

# Legal Bibliography

Build a defensible legal bibliography from BBGpt's multi-engine search, then verify the
authorities that matter. Prefer a short set of strong, checked sources over a long unreviewed
dump.

## Non-negotiable rules

- Never invent an author, title, court, reporter, journal, volume, page, year, DOI, URL, or
  quotation. Omit an unknown field or label the item as needing verification.
- The default client sends query text to `https://bbgpt.battleoftheforms.com`. Do not submit
  privileged, sealed, confidential, client-identifying, or otherwise sensitive facts unless the
  user has approved that service for the matter. Use `BBGPT_BASE_URL` or `--base-url` for an
  approved deployment.
- Treat BBGpt's relevance shortlist and metadata-based citation as discovery aids, not primary
  evidence.
- Treat `bluebook-epps` as the service's citation-formatting policy. It is based on Dan Epps's
  guide at `https://danepps.github.io/bluebook/` (revision May 31, 2026).
- Open and verify the most important sources at their DOI, court, library, publisher, or other
  authoritative record before relying on them in substantive work.
- Distinguish cases and other primary authority from scholarship and other secondary sources.
- Preserve jurisdiction, court, date, edition, and publication-status distinctions. Do not
  silently replace a working paper with a published article unless the records clearly match.
- Report `engine_errors` and `deferred_engines` when they could make the bibliography incomplete.
- Do not use `/clear_cache` in ordinary research.

## Workflow

### 1. Frame the research question

Extract the doctrine, jurisdiction, time range, document types, and known anchor authorities.
If jurisdiction or date would materially change the result and the user has not supplied it,
ask or state the search assumption.

Create two to four focused queries rather than one overloaded query:

1. Doctrine or issue in legal terminology.
2. Known case, statute, author, or canonical title.
3. A narrower jurisdictional or remedial variant.
4. A contrary view, critique, or recent-development query when useful.

### 2. Check the service and choose sources

Run from the skill directory:

```bash
python scripts/bbgpt_client.py health
```

Use the `fast` preset for a quick pass across CrossRef, OpenAlex, and CourtListener:

```bash
python scripts/bbgpt_client.py search \
  "efficient breach contract remedies" \
  --engines fast --no-llm
```

Use `broad` when books, HOLLIS catalog records, and SSRN papers matter:

```bash
python scripts/bbgpt_client.py search \
  "efficient breach theory contract remedies" \
  --engines broad --output /tmp/efficient-breach.json
```

Read [references/api.md](references/api.md) before changing endpoints, consuming SSE directly,
running a batch, or diagnosing a partial response.

### 3. Review the returned evidence

For every response:

- Confirm `success` and inspect `engine_errors`, `deferred_engines`, `cached`, and
  `results_by_engine`.
- Read `llm_enhancement.top_references` as a relevance-ranked shortlist, not an exclusive
  answer. It may contain fewer than three items. Use each item's `selection_reason` to audit
  the match, and remember that the title, authors, and citation metadata come unchanged from
  the selected source record. Use its deterministic `citation` field for display; when enough
  publication-ready records exist, the shortlist prefers complete published citations over
  thin preprint or catalog variants.
- Deduplicate by DOI first, then normalized title plus author and year.
- Prefer a published version with complete metadata over its matching preprint, while retaining
  the preprint link if it is the only accessible copy.
- Prefer HOLLIS or publisher records for books, CrossRef/OpenAlex for publication metadata,
  CourtListener or the relevant court for cases, and SSRN for working-paper status.
- Re-query with a title, author, citation, or DOI when a promising item's metadata is incomplete.

### 4. Verify the authorities that will be delivered

Open the canonical record for each leading item. Confirm at least:

- identity: title and author or case name;
- authority: court/reporter for cases, or journal/publisher and publication status for secondary
  sources;
- locator: volume, first page or chapter/edition, year, DOI, and stable URL where applicable;
- relevance: the source actually bears on the user's issue, based on the primary text or a
  reliable abstract/record.

For high-stakes legal analysis, separately verify any proposition in the primary authority and
check current law. This skill locates and organizes sources; it does not validate that a case is
still good law.

### 5. Format the deliverable

Unless the user requests another structure, return:

1. **Primary authorities** — cases, statutes, regulations, and official materials.
2. **Leading secondary sources** — the strongest articles, books, and treatises.
3. **Additional or recent sources** — useful working papers, critiques, and follow-on work.

For each item provide a citation, stable link/DOI, one sentence on relevance, and a short status
such as `verified`, `metadata verified`, or `candidate—full text not checked`. Preserve BBGpt's
`[I]`/`[SC]` or HTML typography tags only when the requested output supports them; otherwise
render clean plain text. The service intentionally returns citations without a trailing period,
following the Epps style. Add a period only when the citation itself ends a sentence. Spell out
one through four authors; use the first author plus `et al.` for five or more.

Use the type-specific citation rather than forcing every source into an article template. In
particular, retain forthcoming status and URL, working-paper sponsor and number, unpublished-
manuscript status, book edition, chapter editor and container title, case court/reporter, web
date/access date, and statutory code/section metadata when supplied. BBGpt emits independent
full citations; do not manufacture `Id.`, `supra`, signals, or short forms without document and
footnote context.

Conclude with a compact coverage note naming the queries and engines used, any source failures,
and the date of verification.

## Use the client

The bundled client uses only the Python standard library and defaults to the process-safe job
API:

```bash
python scripts/bbgpt_client.py search --help
python scripts/bbgpt_client.py search "query" --engines fast
python scripts/bbgpt_client.py search "query" --engines broad --no-llm
python scripts/bbgpt_client.py search "query" --engines crossref,openalex --sync
python scripts/bbgpt_client.py cite results.json --query "original query"
```

- `--engines fast`: `crossref,openalex,courtlistener`
- `--engines broad`: `hollis,ssrn,crossref,openalex,courtlistener`
- A literal comma-separated subset of those six public engines is also accepted.
- `annas` is available only when requested explicitly and should be used for bibliographic
  metadata, not to acquire or redistribute copyrighted files.
- Do not request CORE or Google Scholar. They were removed from the public service after CORE
  key/timeout failures and repeated Google Scholar HTTP 429 responses.
- LLM selection is on by default. Use `--no-llm` for deterministic metadata collection.
- Use `--sync` for a one-off GET; leave it off for unattended jobs and batches.

The client writes JSON to stdout unless `--output` is supplied. Progress goes to stderr so its
stdout can be piped safely to `jq` or another program.

## Batch discipline

- Check health once, then submit a modest number of jobs. Upstream provider limits still apply.
- Keep a record of the exact query, engine set, LLM mode, and verification date.
- Reuse identical searches when appropriate; the cache key includes query, engine set, and LLM
  mode.
- If a broad search is partial, retry only the missing engine or use a narrower query.
- Stop and report the gap when the requested bibliography depends on an unavailable source.
