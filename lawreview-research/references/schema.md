# Compatible law-corpus schema

## Contents

1. Required SQLite capabilities
2. Core tables
3. FTS tables
4. Optional snapshot metadata
5. Data and rights boundary

## 1. Required SQLite capabilities

The bundled CLI expects SQLite with FTS5 enabled. It opens the database in read-only mode and does not create or migrate tables.

## 2. Core tables

The queries use these fields. Additional fields are permitted.

```sql
CREATE TABLE documents (
  document_key TEXT PRIMARY KEY,
  archive_remote_path TEXT,
  source_id INTEGER,
  journal_hint TEXT,
  member_path TEXT,
  page_count INTEGER,
  char_count INTEGER,
  updated_at TEXT
);

CREATE TABLE pages (
  id INTEGER PRIMARY KEY,
  page_key TEXT,
  document_key TEXT,
  page_number INTEGER,
  inner_path TEXT,
  local_path TEXT,
  archive_remote_path TEXT,
  chars INTEGER,
  text TEXT
);

CREATE TABLE metadata_guess (
  document_key TEXT PRIMARY KEY,
  title_guess TEXT,
  authors_json TEXT,
  year_guess INTEGER,
  confidence TEXT
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  document_key TEXT,
  chunk_index INTEGER,
  page_start INTEGER,
  page_end INTEGER,
  archive_remote_path TEXT,
  source_id INTEGER,
  journal_hint TEXT,
  member_path TEXT,
  context_header TEXT,
  text TEXT
);

CREATE TABLE citations (
  citation_text TEXT,
  normalized_cite TEXT,
  parser TEXT,
  citation_type TEXT,
  page_number INTEGER,
  local_path TEXT,
  document_key TEXT
);
```

## 3. FTS tables

`page_fts` must use the `pages.id` value as its rowid and expose page text as column 0. `chunk_fts` must use `chunks.id` as rowid and expose chunk text as column 1 because the bundled queries call SQLite's `snippet()` with those column positions.

A representative arrangement is:

```sql
CREATE VIRTUAL TABLE page_fts USING fts5(text, content='pages', content_rowid='id');
CREATE VIRTUAL TABLE chunk_fts USING fts5(context_header, text, content='chunks', content_rowid='id');
```

The originating indexer is responsible for keeping content and FTS rows synchronized.

## 4. Optional snapshot metadata

When `<database>.json` exists, `stats` can read precomputed keys including `counts`, `document_page_total`, `document_char_total`, `journal_count`, `max_document_updated_at`, and `snapshot_created_at`. Without a sidecar, it calculates available counts from the database.

## 5. Data and rights boundary

This schema describes an index; it does not confer rights to acquire, OCR, store, quote, or redistribute source documents. Use synthetic, public-domain, licensed, or otherwise authorized material, and keep private corpora outside this repository.
