# Word OOXML ground truth

## Contents

1. Authority and donor policy
2. Footnote target bookmark
3. Field shapes observed in Word 16
4. Formatting inheritance
5. Bookmark registry rules
6. Footnote cache evaluation
7. Update semantics
8. Package preservation

## 1. Authority and donor policy

Use Microsoft Word's persisted output as the serializer specification. Generate
organic cases with `Range.InsertCrossReference`, save as DOCX, inspect the
package, and validate at least one case against the dialog path. When Word's
output conflicts with a generic recipe, follow Word.

Keep one donor per reference choice. Transplant donor nodes and substitute only
the bookmark name, cache text, insertion formatting, and collision-sensitive
IDs. Ignore rsids when comparing semantic structure.

## 2. Footnote target bookmark

The bookmark belongs in `word/document.xml` and wraps only the run containing
the target note mark:

```xml
<w:bookmarkStart w:id="7" w:name="_Ref123456789"/>
<w:r>
  <w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>
  <w:footnoteReference w:id="37"/>
</w:r>
<w:bookmarkEnd w:id="7"/>
```

Do not bookmark the note text or place the bookmark in `footnotes.xml`. Do not
include a paragraph mark. Generate a unique integer ID after scanning every
Word story part and a unique `_Ref` plus nine-digit name under 40 characters.

## 3. Field shapes observed in Word 16

### Hyperlinked footnote number

Word writes a five-run complex field:

```xml
<w:r><w:fldChar w:fldCharType="begin"/></w:r>
<w:r><w:instrText xml:space="preserve"> NOTEREF _Ref123456789 \h </w:instrText></w:r>
<w:r><w:fldChar w:fldCharType="separate"/></w:r>
<w:r><w:t>34</w:t></w:r>
<w:r><w:fldChar w:fldCharType="end"/></w:r>
```

The leading/trailing instruction spaces and `xml:space="preserve"` are
significant. Each marker and instruction lives in its own run. The cached result
is present and correct at delivery.

### Non-hyperlinked footnote number

Word 16 writes a simple field, not the five-run shape:

```xml
<w:fldSimple w:instr=" NOTEREF _Ref123456789 ">
  <w:r><w:t>34</w:t></w:r>
</w:fldSimple>
```

### Formatted footnote number

Word adds `\f`. The cached-result run includes
`<w:rStyle w:val="FootnoteReference"/>`. Merge that donor-only property with
the insertion formatting rather than replacing either one.

### Position reference

Word 16 persists the above/below choice as `REF`, not NOTEREF:

```text
 REF _Ref123456789 \p \h
```

An organic position field can initially lack `separate` and cache runs. Reuse
that observed donor and mark the manifest cache confidence as degraded because
above/below requires pagination.

### Bookmark and heading text

Use `REF bookmark_name \h`. For a user bookmark, preserve its name and exact
span. For a heading, wrap the exact paragraph content (not `w:pPr` or paragraph
mark) in a hidden reusable bookmark. Cache the bookmarked visible text.

## 4. Formatting inheritance

In a plainly styled donor, Word may omit field-run `w:rPr`. That does not mean
an injector may always omit it.

When insertion occurs inside directly formatted text, Word copies the insertion
run's properties to every complex-field run: begin, instruction, separator,
result, and end. A verified manuscript case produced this on all five runs:

```xml
<w:rPr>
  <w:rFonts w:ascii="Garamond Premr Pro"
            w:eastAsia="Times New Roman"
            w:hAnsi="Garamond Premr Pro"/>
  <w:sz w:val="19"/>
  <w:szCs w:val="19"/>
</w:rPr>
```

Therefore retain the marker run until serialization, deep-copy its complete
`w:rPr`, and attach the copy to every transplanted field run. For a donor run
with semantic properties such as `FootnoteReference`, merge donor properties
by tag over the insertion properties. Apply the insertion formatting to the
inner result run of `w:fldSimple` too.

Validate formatting through both XML inspection and Word's effective
`Field.Result.Font` values. Font name and size alone are insufficient when the
source includes italic, small caps, language, complex-script size, color, or
proofing properties; copy the entire `w:rPr`.

## 5. Bookmark registry rules

Key bookmarks by effective range, not citation text or target ID alone.

1. Inspect contiguous bookmark starts immediately before the target's first
   node and matching ends immediately after its last node.
2. Prefer an existing `_Ref` bookmark that exactly spans the target.
3. Otherwise reuse an exact user bookmark.
4. Otherwise mint one hidden bookmark.
5. Reuse that bookmark for every later reference to the same exact range.

Reject duplicate names or IDs. Do not reuse a bookmark that includes extra text
or a paragraph mark. Do not "repair" unrelated stale bookmarks.

## 6. Footnote cache evaluation

Build a map from note definition ID to displayed ordinal by walking main-story
`w:footnoteReference` elements in document order, including descendants in
tables and text boxes.

Exclude:

- definitions with `w:type` (separator and continuation records);
- references carrying `w:customMarkFollows` from automatic numbering.

Apply global/section `w:footnotePr`:

- `w:numStart` sets the initial or section start;
- `w:numRestart` supports continuous and each-section directly;
- each-page restart is layout-dependent and must be degraded;
- `w:numFmt` renders decimal, Roman, letter, or Chicago symbols.

Do not confuse the note definition ID with the displayed number. For example, a
document with three nonautomatic records can display note 34 while its
`w:footnoteReference/@w:id` is 37.

## 7. Update semantics

Body Ctrl+A/F9 and `document.Fields.Update()` do not reliably update fields in
the footnote story. Iterate `StoryRanges` and every `NextStoryRange`, or click in
the footnote pane and update it explicitly. Print/PDF update behavior depends on
Word settings.

Do not set `w:dirty` and do not add `w:updateFields`. Those flags can cause
modal prompts or blank-until-update behavior and do not solve story coverage.

## 8. Package preservation

Read every ZIP entry with its original `ZipInfo`; rewrite only modified XML
parts; emit entries in their original order. Preserve untouched bytes,
compression metadata, content types, relationships, tracked changes, comments,
rsids, and metadata. Write to a sibling temporary file and atomically replace
the requested destination.
