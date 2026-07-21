# Contributing

Contributions should preserve the central rule of this repository: legal sources and document structures must be verified rather than guessed.

## Skill changes

- Keep each skill's YAML frontmatter limited to `name` and `description`.
- Put essential workflow instructions in `SKILL.md`; put detailed schemas and background in `references/`.
- Never include credentials, private infrastructure, confidential documents, copyrighted corpora, or production database snapshots.
- Use synthetic, public-domain, or appropriately licensed test fixtures.
- State jurisdictional, temporal, source-access, and verification limits explicitly.

## Checks

Run before opening a pull request:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_skills.py
```

Windows-only Word automation should be tested separately with Microsoft Word and `pywin32`. Record the Word version and the operations tested.
