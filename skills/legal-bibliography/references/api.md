# BBGpt API contract

Production base URL: `https://bbgpt.battleoftheforms.com`

The bundled client reads `BBGPT_BASE_URL` and otherwise uses the production URL. A command-line
`--base-url` overrides both.

Queries sent to a remote deployment leave the user's machine. Do not submit confidential or
client-identifying facts unless that deployment's access, logging, retention, and privacy terms
are acceptable for the matter.

## Health

`GET /health` returns readiness, feature flags, and public engine status. Check it before a
batch. An engine marked `ok` means it is registered, not that every upstream request will
succeed.

## Engines

| Engine | Best use | Notes |
|---|---|---|
| `hollis` | Books, treatises, definitive catalog metadata | Playwright-backed; up to 5 results in the filtered response |
| `ssrn` | Working papers and forthcoming scholarship | Useful for publication-status discovery |
| `annas` | Optional book metadata | Request explicitly; do not use the skill to acquire or redistribute copyrighted files |
| `crossref` | DOI and journal metadata | Fast, authoritative publication registry |
| `openalex` | Broad scholarship and citation discovery | Fast; strong complement to CrossRef |
| `courtlistener` | U.S. cases | Verify important cases with the court or citator |

These six names are the complete public engine contract and the default engine set. CORE and
Google Scholar are intentionally unavailable because live CORE searches lacked a usable API
key and timed out, while Google Scholar repeatedly returned HTTP 429. Do not send those names.

## Synchronous search

`GET /api/search`

| Parameter | Type | Default | Limits |
|---|---|---|---|
| `q` | string | required | nonempty |
| `engines` | comma-separated string | all six public engines | names from the table above |
| `use_llm` | boolean string | `true` | `true`, `false`, `1`, or `0` |
| `top_per_engine` | integer | `3` | 1–50; HOLLIS uses up to 5 |
| `timeout` | integer seconds | `90` | 10–300 |

Important response fields:

```json
{
  "success": true,
  "query": "...",
  "results": [],
  "results_by_engine": {"crossref": 10},
  "total_results": 3,
  "total_found": 10,
  "engines_used": ["crossref"],
  "search_time_seconds": 1.2,
  "cached": false,
  "citation_style": {
    "id": "bluebook-epps",
    "source": "https://danepps.github.io/bluebook/",
    "revision": "2026-05-31"
  },
  "llm_enhancement": {
    "enabled": true,
    "top_references": []
  },
  "engine_errors": {},
  "deferred_engines": []
}
```

`authors`, `year`, `journal`, `journal_abbr`, `volume`, `first_page`, `doi`, `url`, and
`work_type` are optional because source schemas differ. `journal` preserves the full source
title; `journal_abbr` is the abbreviation used by the formatter when present.

`llm_enhancement.top_references` contains zero to three relevance-selected original records.
The model returns only a record index and short `selection_reason`; it cannot rewrite title,
author, or citation metadata. Each selected record also includes a deterministic `citation`.
When at least three publication-ready candidates exist, selection is limited to records with
enough journal/publisher or reporter metadata to render a full citation. Source prestige is only
a tie-breaker after direct query relevance and citation completeness.

## Asynchronous jobs

`POST /api/search` accepts the same parameters as a JSON object. `engines` is a comma-separated
string. The response is HTTP 202:

```json
{
  "success": true,
  "job_id": "...",
  "status": "queued",
  "status_url": "/api/search/jobs/<job_id>",
  "stream_url": "/api/search/jobs/<job_id>/stream"
}
```

Poll `GET /api/search/jobs/<job_id>`. Terminal states are `completed` and `failed`; a completed
job's normal search response is in `result`. Jobs expire after one hour, and the process-safe
store retains at most 200.

`GET /api/search/jobs/<job_id>/stream` emits JSON SSE events:

```text
data: {"type":"job_status","status":"running",...}

data: {"type":"result","result":{...},...}

data: {"type":"done",...}
```

Successful streams contain exactly one `done`. Error streams emit an `error` event.

## Browser/UI stream

`GET /stream?query=<query>&engines=<list>&all=0&use_llm=1` emits typed JSON SSE. Types include
`engine_started`, `engine_done`, `top_references`, `source_header`, `citation`, `log`, `error`,
and `done`. Caddy does not buffer this route. Prefer the job API for agent automation.

## Citations and raw data

- `POST /api/citations` with `{"query":"...","results":[...]}` returns citations formatted
  deterministically from the supplied source metadata. The response and each citation identify
  the `bluebook-epps` policy and link its style source. Citations use `<i>` and `<sk>` rich-text
  markers and intentionally have no trailing period. The formatter writes out up to four authors
  and begins `et al.` at five.
- The browser's **Copy for Word** actions convert those tags to a rich `text/html` clipboard
  flavor using Word-compatible paragraphs, inline italics, and inline
  `font-variant: small-caps`; `text/plain` is included as a fallback. In Windows Word, paste
  with **Keep Source Formatting**. API clients still receive the citation string and are
  responsible for rendering its tags.
- `GET|POST /api/raw_search` returns unprocessed per-engine outputs.
- `GET /raw_results?job_id=<job_id>` returns the raw output attached to an explicit job.
- `GET|POST /api/hollis` performs a HOLLIS-only search (`q`, `top`, `timeout`).
- `GET /cache_stats` returns cache metrics.
- `POST /clear_cache` is administrative. It is disabled without `BBGPT_ADMIN_TOKEN` and
  requires `X-BBGPT-Admin-Token`. Never call it as part of ordinary research.

## Failure handling

- A non-2xx response normally includes `error` or `message`.
- A successful HTTP response can still be partial. Inspect `engine_errors` and
  `deferred_engines`.
- Do not cache or present a partial response as a complete survey without disclosure.
- The cache contract is normalized query + engine set + LLM mode. Healthy results may remain
  cached for up to 14 days.
- Keep concurrency modest and retry transient upstream failures with a narrower engine set.

## Citation-policy boundary

The Epps style's signals, explanatory parentheticals, `Id.`, `supra`, and case short forms need
document and prior-footnote context. BBGpt's stateless API therefore returns independent full
citations and does not synthesize those context-dependent forms.
