# Injection plan and manifest schema

## Contents

1. Plan envelope
2. Target variants
3. Placement
4. Reference kinds
5. Manifest

## 1. Plan envelope

Pass either a JSON array of request objects or an object with a `references`
array:

```json
{"references": []}
```

Each request contains `target`, `placement`, `kind`, and `hyperlink`.

## 2. Target variants

### Footnote target

```json
{"kind": "footnote", "id": 37}
```

`id` is `w:footnoteReference/@w:id`, not the displayed number.

### Existing bookmark target

```json
{"kind": "bookmark", "name": "UserTarget"}
```

The named bookmark must exist exactly once, balance within one container, and
contain nonempty bookmarkable content.

### Heading target

```json
{"kind": "heading", "paragraph_index": 12}
```

`paragraph_index` is 1-based among body-descendant paragraphs in document
order. Upstream code should identify the semantic heading object; do not locate
it by fuzzy text inside the injector.

## 3. Placement

Body placement:

```json
{
  "part": "word/document.xml",
  "marker": "[[REF:CONCLUSION]]"
}
```

Footnote placement:

```json
{
  "part": "word/footnotes.xml",
  "footnote_id": 43,
  "marker": "[[XREF:GILSON]]"
}
```

The marker must occur in exactly one `w:t` inside the selected scope.

## 4. Reference kinds

- `footnote-number` with a footnote target.
- `formatted-footnote-number` with a footnote target.
- `position` with a footnote target.
- `bookmark-text` with an existing bookmark target.
- `heading-text` with a heading target.

`hyperlink` defaults to `true`. The bundled Word corpus includes hyperlinked and
non-hyperlinked footnote-number donors; secondary REF donors currently cover
the Word dialog's hyperlinked default.

## 5. Manifest

The injector writes:

```json
{
  "source": "input.docx",
  "output": "output.docx",
  "references": [{
    "index": 1,
    "reference_kind": "footnote-number",
    "location": {
      "part": "word/footnotes.xml",
      "footnote_id": 43,
      "marker": "[[XREF:GILSON]]"
    },
    "target": {"kind": "footnote", "id": 37},
    "bookmark_name": "_Ref123456789",
    "bookmark_id": 7,
    "bookmark_reused": false,
    "computed_cache": "34",
    "confidence": "exact",
    "warnings": [],
    "field_instruction": " NOTEREF _Ref123456789 \\h "
  }]
}
```

Treat `confidence: degraded` as an explicit delivery warning. Keep the manifest
beside internal QA artifacts unless the user requests it; the DOCX is normally
the only final deliverable.
