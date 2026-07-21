---
name: bluebook-review
description: Review and correct legal citations in Microsoft Word DOCX manuscripts using the current Bluebook Style — Epps Version guide and CSL implementation from danepps/bluebook. Use for law-review footnotes, citation audits, first and short forms, Id. and supra usage, pincites, source-type formatting, signals, parentheticals, typography, Zotero citation fields, and delivery of a reviewed or redlined Word document. This skill applies the Epps materials, not the proprietary official Bluebook, and must not invent missing citation metadata.
---

# Bluebook Review

Review a Word manuscript against the current public **Bluebook Style — Epps Version** materials, preserve the document's citation machinery, and deliver a verified reviewed copy plus an issue log.

## Attribution and authority

Read [references/attribution.md](references/attribution.md) before fetching or applying the upstream materials.

Credit **Professor Daniel Epps** for the Epps version and preserve the upstream CC BY-SA 4.0 license. Also preserve the upstream credits to **Bruce D'Arcus**, **Nancy Sims**, and **Patrick O'Brien**. Do not imply that Professor Epps, Washington University, the upstream contributors, or the publishers of *The Bluebook* endorse this skill.

Treat the sources in this order:

1. The commit-pinned upstream `README.md` for the Epps guide, data-entry rules, implementation choices, and known limitations.
2. The matching `BluebookDSEStyle.csl` for exact behavior implemented by the Epps Zotero/CSL style.
3. The manuscript's context for note sequence, signals, parentheticals, and source identity.

The Epps repository is a Zotero/CSL style and practical guide, not a complete copy of the proprietary official Bluebook. Never claim comprehensive official-Bluebook compliance when a question falls outside the upstream materials. Flag the issue for human review instead.

## 1. Fetch and read the rules

From this skill directory, fetch a commit-pinned upstream bundle:

```bash
python scripts/fetch_epps_bluebook.py --output-dir work/epps-bluebook
```

The command downloads the upstream guide, CSL, and license, records SHA-256 hashes, and writes `source.json` containing the resolved Git commit. It does not vendor upstream content into this skill.

Read `work/epps-bluebook/README.md` completely before reviewing the manuscript. Inspect the CSL whenever the exact rendering, source-type branch, locator behavior, or short-form behavior matters. Useful searches include:

```bash
rg -n '^#{2,4} |journal article|case|statute|book|webpage|supra|Id\.|pincite|signal|parenthetical|Known limitations' \
  work/epps-bluebook/README.md
rg -n 'near-note-distance|subsequent|ibid|locator|jurisdiction|container-title|title-short' \
  work/epps-bluebook/BluebookDSEStyle.csl
```

If network access is unavailable, use `--offline` only when a previously fetched bundle passes its recorded hash checks. State the cached commit and fetch time in the review.

## 2. Preserve and inspect the Word document

- Preserve the source DOCX. Write a new reviewed copy.
- Use the active document/DOCX tooling to render and inspect the manuscript before editing.
- Create a machine-readable inventory of footnotes, endnotes, and citation fields:

```bash
python scripts/inspect_docx_citations.py manuscript.docx \
  --output work/citation-inventory.json
```

- Inventory body citations, footnotes, endnotes, tables, text boxes, comments, tracked changes, bookmarks, and citation fields.
- Determine whether each citation is static text, a live Zotero field, another field type, or ordinary prose.
- Record note number, citation text, source type, first/subsequent status, locator, and field status.

Never flatten, unlink, or directly overwrite a live Zotero field merely to change its displayed result. Preserve field codes and citation-item data. Correct Zotero metadata or field inputs when the runtime can do so safely; otherwise attach a comment explaining the required Zotero change.

The inventory's `reference_order` follows main-document note-reference order; it is not guaranteed to equal the displayed note number when the document uses custom marks, restarts, or unusual numbering. Resolve displayed numbering through Word or the active document tooling before reporting a note number.

## 3. Review in document order

Review the full citation sequence, not isolated strings. For each citation:

1. Confirm source identity and required metadata. Do not invent authors, titles, courts, reporters, journals, volumes, pages, dates, URLs, or publication status.
2. Apply the Epps source-type instructions for the full citation.
3. Check pincites and locator labels.
4. Check immediate and later short forms, including note-distance behavior described by the upstream guide.
5. Check signals, explanatory parentheticals, and citation ordering only to the extent covered by the guide and manuscript context.
6. Check rich-text typography, spacing, punctuation, small caps, and italics.
7. Distinguish an Epps implementation choice or known CSL limitation from an asserted Bluebook rule.

When metadata is missing or identity is uncertain, leave the citation intact and add a precise comment such as `Needs reporter first page` or `Verify whether this is the published article or SSRN version`.

## 4. Apply corrections safely

Default to a reviewed DOCX with tracked changes or comments when the available Word tooling supports them. If the user requests a clean copy, still retain a separate issue log.

- Apply high-confidence corrections to static citation text.
- Preserve surrounding footnote formatting, styles, cross-references, bookmarks, and note numbering.
- For live Zotero citations, prefer corrections to the relevant Zotero fields identified by the Epps guide, such as Journal Abbr, Short Title, locator, Prefix, or Extra-field values. Do not simulate a Zotero Refresh by rewriting cached field text.
- Do not silently change substantive propositions, quotations, source selections, or pincites.
- Do not convert footnotes to endnotes or alter manuscript pagination unless required and disclosed.

## 5. Validate and deliver

After editing:

1. Reopen the DOCX without a repair prompt.
2. Confirm Zotero and Word fields remain fields.
3. Render source and reviewed copies through the same engine.
4. Compare page count and inspect every changed page, especially complete footnote blocks and page breaks.
5. Re-read each corrected citation in sequence and confirm that short forms still point to the intended source.

Deliver:

- the reviewed DOCX;
- a concise issue log with note/location, original text, correction or recommendation, upstream guide section, confidence, and unresolved metadata;
- a provenance line naming `danepps/bluebook`, the resolved commit, fetch date, and CC BY-SA 4.0 license;
- a limitations note identifying any matters outside the Epps guide or requiring Zotero/human review.

Do not add attribution prose inside the user's manuscript unless requested; put it in the accompanying review report.
