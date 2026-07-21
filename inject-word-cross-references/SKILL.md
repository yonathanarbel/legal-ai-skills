---
name: inject-word-cross-references
description: Inject, repair, inspect, and differentially validate Microsoft Word cross-references directly in DOCX packages while preserving native Word behavior, formatting, bookmarks, cached results, and untouched package parts. Use for Word footnote or endnote cross-references, NOTEREF and REF fields, "supra note" citations, heading/bookmark references, stale hard-coded note numbers, cross-reference renumbering, hyperlink targets, field-story update problems, or OOXML cross-reference fidelity testing.
---

# Inject Word Cross-References

Create cross-references that behave like references inserted through Word's
Cross-reference dialog. Treat persisted Word output as ground truth; do not
invent field structures from OOXML documentation alone.

## Non-negotiable rules

- Preserve the source file. Write a new DOCX unless the user explicitly asks to
  replace it and the file is not open.
- Resolve targets semantically. Never assume a footnote's `w:id` equals its
  displayed number; custom marks and separator records make that unsafe.
- Place a footnote target bookmark around the main-story
  `w:footnoteReference`, never around content in `footnotes.xml`.
- Reuse an existing bookmark when it spans the exact effective target range.
  Multiple references to the same note must share one bookmark.
- Transplant the insertion run's `w:rPr` onto every field run. Word does this
  when the surrounding document uses direct formatting; omitting it causes the
  reference number to visibly break the footnote style.
- Emit a clean, nonempty cache. Do not set `w:dirty` or add `w:updateFields`.
- Preserve ZIP entry order and untouched parts byte-for-byte. Do not clean up
  rsids, stale bookmarks, metadata, or unrelated document cruft.
- End every delivered DOCX edit with structural validation, a Word update test
  when Word is available, and render/visual review.

Read [references/word-ooxml.md](references/word-ooxml.md) before changing field
serialization, bookmark spans, numbering, or formatting behavior. Read
[references/workflow-and-testing.md](references/workflow-and-testing.md) before
editing a real document or claiming behavioral equivalence. Read
[references/plan-schema.md](references/plan-schema.md) when building a plan or
interpreting a manifest.

Install the deterministic XML dependency before running the bundled CLI:

```bash
python -m pip install -r requirements.txt
```

The injector and structural validator are cross-platform. The Word differential
tools require Windows, Microsoft Word, and `pywin32`.

## Workflow

### 1. Inspect and resolve candidates

Unzip/read `word/document.xml` and `word/footnotes.xml`. Find explicit static
references (`supra note 12`) and drafting placeholders (`supra --`, `[X supra]`).
Resolve each citation to an earlier full citation using author/title identity;
skip ambiguous targets rather than guessing.

Build the displayed-number map by walking automatic `w:footnoteReference`
elements in document order. Exclude separator/continuation definitions and
references carrying `w:customMarkFollows`.

### 2. Place unique markers

Replace only the number or placeholder token with a unique marker, preserving
the original run and its `w:rPr`, for example:

```text
supra note [[XREF:GILSON]]
Contract Theory, supra [[XREF:CONTRACT-THEORY]]
```

Each marker must be wholly contained in one `w:t`. If Word split the token
across runs, merge or place the marker surgically while preserving formatting.
Do not insert at a bookmark's opening edge.

### 3. Create a JSON plan

For a footnote-story reference:

```json
{
  "references": [{
    "target": {"kind": "footnote", "id": 37},
    "placement": {
      "part": "word/footnotes.xml",
      "footnote_id": 43,
      "marker": "[[XREF:GILSON]]"
    },
    "kind": "footnote-number",
    "hyperlink": true
  }]
}
```

The target and referring values are OOXML note IDs, not displayed ordinals.
See the plan reference for heading and existing-bookmark examples.

### 4. Inject and validate

Run the bundled implementation from the skill directory:

```powershell
python scripts/docx_xref_cli.py inject input.marked.docx output.docx `
  --plan plan.json --manifest output.xref-manifest.json
python scripts/docx_xref_cli.py validate output.docx
```

For an organic/injected twin:

```powershell
python scripts/docx_xref_cli.py diff organic.docx injected.docx
```

The serializer uses Word-harvested donor fragments bundled in
`scripts/docx_xref/donors/`, substitutes target names and caches, and carries
the marker run's formatting onto the field exactly as Word does.

### 5. Verify behavior in Word

Open with `OpenAndRepair=False` and alerts enabled for a manual release check.
Update every story, not only `document.Fields`:

```python
for story_type in range(1, 18):
    try:
        story = document.StoryRanges(story_type)
    except Exception:
        continue
    while story is not None:
        story.Fields.Update()
        story = story.NextStoryRange
```

Confirm baseline cache values, then add one earlier footnote and confirm every
affected result shifts. Inspect each result's font name, size, emphasis, and
language against adjacent footnote text. Use `scripts/release_gate.py` for the
automated Word differential operations.

### 6. Render and deliver

Render the final DOCX to page PNGs using the active document skill's renderer.
Inspect every changed page at full resolution and compare total page count with
the source. For large documents, raster-diff source and result first, then
inspect every materially changed page and investigate unexpected changed pages.
Deliver only the final DOCX unless the user requests manifests or QA artifacts.

## Supported targets and cache policy

- `footnote-number`: Word-native NOTEREF; normal result formatting.
- `formatted-footnote-number`: NOTEREF with `\f`; retains the
  `FootnoteReference` result style in addition to insertion formatting.
- `position`: Word persists this choice as `REF ... \p`; pagination is required
  for an exact above/below cache.
- `bookmark-text`: REF to an existing named bookmark.
- `heading-text`: REF to an exact heading paragraph range with a reusable hidden
  bookmark.

Per-page footnote restarts and position fields are degraded-cache cases. Emit a
best guess, set manifest confidence to `degraded`, and report the required Word
update. Do not silently emit an empty result.

Paragraph-number switches (`\r`, `\w`, `\n`) require a `numbering.xml`
evaluator and are outside this skill's deterministic cache support. Stop or use
Word as the finishing authority rather than guessing.

## Bundled tools

- `scripts/docx_xref_cli.py`: inject, validate, and semantic-diff CLI.
- `scripts/build_ground_truth.py`: generate Word-authored donor cases through
  the Word object model.
- `scripts/harvest_donors.py`: harvest exact field fragments from organic DOCX
  samples.
- `scripts/semantic_dump.py`: create stable semantic field/bookmark reports.
- `scripts/probe_update_semantics.py`: demonstrate body-versus-footnote story
  update coverage.
- `scripts/release_gate.py`: Word update, renumber, deletion, conversion,
  tracked-change, and PDF-export differential gate.
