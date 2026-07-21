# Legal AI Skills

Three open, reusable agent skills for rigorous legal scholarship and legal-document workflows:

| Skill | What it does |
| --- | --- |
| [`legal-bibliography`](skills/legal-bibliography/) | Finds, ranks, verifies, and formats legal authorities through a structured multi-engine research workflow. |
| [`inject-word-cross-references`](skills/inject-word-cross-references/) | Injects Word-native footnote and bookmark cross-references into DOCX packages while preserving formatting and package fidelity. |
| [`lawreview-research`](skills/lawreview-research/) | Searches a compatible SQLite/FTS law-review corpus, expands passage context, finds citing documents, and evaluates retrieval quality. |

The skills use the portable `SKILL.md` folder convention and are designed for agents that support skill discovery, including OpenAI Codex and other compatible runtimes.

## Install

Clone the repository, then copy or symlink the desired skill folder into your agent's skills directory. For Codex:

```bash
git clone https://github.com/yonathanarbel/legal-ai-skills.git
mkdir -p ~/.codex/skills
cp -R legal-ai-skills/skills/legal-bibliography ~/.codex/skills/
cp -R legal-ai-skills/skills/inject-word-cross-references ~/.codex/skills/
cp -R legal-ai-skills/skills/lawreview-research ~/.codex/skills/
```

Install the Python dependency required by the Word cross-reference tooling:

```bash
python -m pip install "lxml>=5"
```

The law-review corpus CLI uses only the Python standard library. Word behavioral verification on Windows additionally requires Microsoft Word and `pywin32`.

## Important boundaries

- These are research and document-engineering tools, not legal advice.
- Verify important propositions in primary authority and check that the law remains current.
- Do not send confidential, privileged, sealed, or client-identifying queries to a remote service unless its privacy terms are acceptable for the matter.
- The repository does not contain a law-review corpus. Users must supply a compatible database containing material they are authorized to process.
- OCR text and inferred metadata are provisional and should be checked against authoritative copies.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_skills.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and testing expectations.

## License

Apache License 2.0. See [LICENSE](LICENSE).
