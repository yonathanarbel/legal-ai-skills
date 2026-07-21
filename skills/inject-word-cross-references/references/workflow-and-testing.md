# Real-document workflow and differential testing

## Contents

1. Candidate discovery
2. Resolving citations safely
3. Marker preparation
4. Structural checks
5. Word differential battery
6. LibreOffice and rendering
7. Failure diagnosis

## 1. Candidate discovery

Extract each automatic footnote's visible text and scan for:

- `supra note N`, `infra note N`, and `see note N`;
- `supra --`, `supra ___`, bracketed author-plus-supra placeholders;
- repeated short-form author/title citations with a static number;
- existing NOTEREF/REF fields that lack a target or have a stale cache.

Report referring displayed number, referring note ID, citation context, proposed
target displayed number, proposed target note ID, and confidence. Do not mutate
while discovery is still ambiguous.

## 2. Resolving citations safely

Match a short citation to an earlier full citation using author and title, not
number proximity. A single footnote may contain several full citations; this is
still a valid target because cross-references point to the footnote mark.

If multiple plausible earlier citations exist, leave the placeholder unchanged
and report it. Never use the currently typed static number as sole authority:
it may already be stale because earlier footnotes were added.

Construct the displayed-number map from document order. Validate the proposed
target by printing its full footnote text before injection.

## 3. Marker preparation

Use a unique marker for every insertion location, even when targets repeat.
Repeated targets should produce distinct fields sharing one bookmark.

Replace only the placeholder token. Preserve the containing `w:r`, its complete
`w:rPr`, and surrounding text. If the placeholder occupies a dedicated run,
replace only that run's `w:t`. If embedded, split into leading text, field, and
trailing text with cloned run properties.

Reject markers that:

- appear more than once in the scoped note;
- are split across `w:t` nodes;
- share a run with drawings, tabs, breaks, or other non-text content;
- sit immediately after a bookmark start.

## 4. Structural checks

Run `validate` before opening Word. Require:

- every XML part parses;
- bookmark starts/ends balance by story and ID;
- bookmark IDs and names are unique under the skill's package-global policy;
- complex field begin/separate/end nesting is valid;
- simple fields retain a nonempty result;
- every instruction has preserved leading/trailing spaces where observed;
- no injected field carries `w:dirty`;
- settings contain no injected `w:updateFields`;
- all untouched ZIP entries are byte-identical and entry order is unchanged.

Inspect each new field's instruction, cache, result properties, bookmark name,
target note ID, and confidence in the JSON manifest.

## 5. Word differential battery

Maintain an organic twin and an injected twin with identical visible content.
Run both through the same operations and compare all story text after each.

1. **Open cleanliness:** open with no repair or conversion path. Any repair or
   unreadable-content warning fails.
2. **Baseline update:** update every story and compare visible story text.
3. **Renumber:** add an automatic footnote before the target, update every
   story, and confirm both results shift identically.
4. **Deletion:** delete the target mark using the same UI/COM operation in both,
   update, and compare the resulting error or survival behavior.
5. **Hyperlink:** manually Ctrl+click the result and verify the selection moves
   to the target mark. Field code containing `\h` is necessary but not a full UI
   test.
6. **Conversion:** convert footnotes to endnotes and back; compare behavior.
7. **Tracked changes:** delete under tracking, accept/update, then repeat with
   rejection; compare behavior.
8. **Formatting:** compare `Field.Result.Font` and the result run's complete
   `w:rPr` with adjacent citation text.
9. **Save/reopen:** save, close, reopen, update, and compare.
10. **Export:** export both to PDF and raster-diff every page.

Use `scripts/release_gate.py organic.docx injected.docx --output-dir gate` for
the automatable subset. Keep hyperlink following and repair-prompt observation
as manual release checks because Word UI automation can block or suppress the
very prompt being tested.

## 6. LibreOffice and rendering

Use LibreOffice only as an interop oracle or optional cache-repair pass. It can
rewrite the package broadly, strip switches, or restructure generated content;
do not make it mandatory when tracked changes or diff hygiene matter.

For visual QA:

1. Render source and result to PDFs through the same engine.
2. Confirm equal page count unless a deliberate reflow is expected.
3. Rasterize all pages at the same scale.
4. Compute per-page pixel differences.
5. Inspect every materially changed page at full resolution.
6. Investigate unexpected changed pages; tiny glyph-antialiasing boxes can
   arise from separate export sessions, but layout-sized changes cannot be
   dismissed.

Cross-reference edits often affect only footnote pages. Inspect the entire
footnote block, separator, body/footnote collision area, page number, and next
page break on every affected page.

## 7. Failure diagnosis

- **Number uses wrong font/size:** marker `w:rPr` was discarded or applied only
  to the result. Copy it to every field run.
- **Literal field code or blank result:** malformed nesting, missing separator,
  or missing cache for a field shape that Word normally evaluates at birth.
- **No renumber:** bookmark is in the note story, target is static text, or the
  footnote story was not updated.
- **Wrong number but correct target ID:** cache evaluator treated IDs as
  ordinals, counted custom marks, or ignored section restart rules.
- **Duplicate target bookmarks:** registry keyed by request instead of exact
  effective range.
- **Jump lands near target rather than on it:** bookmark span includes extra
  text/paragraph mark or collapsed during deletion.
- **Unreadable-content repair:** invalid field nesting, duplicate bookmark
  names/IDs, cross-container bookmarks, or malformed XML serialization.
- **Unexpected broad diff:** package was round-tripped through a general DOCX
  library or LibreOffice instead of patching only the required parts.
