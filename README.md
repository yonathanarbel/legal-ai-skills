# Legal AI Skills

Four open, reusable agent skills for rigorous legal scholarship and legal-document workflows:

| Skill | What it does |
| --- | --- |
| [`bluebook-review`](bluebook-review/) | Reviews and corrects citations in Word manuscripts using a commit-pinned copy of Dan Epps's public Bluebook style guide and CSL implementation. |
| [`legal-bibliography`](legal-bibliography/) | Finds, ranks, verifies, and formats legal authorities through a structured multi-engine research workflow. |
| [`inject-word-cross-references`](inject-word-cross-references/) | Injects Word-native footnote and bookmark cross-references into DOCX packages while preserving formatting and package fidelity. |
| [`lawreview-research`](lawreview-research/) | Searches a compatible SQLite/FTS law-review corpus, expands passage context, finds citing documents, and evaluates retrieval quality. |

### Bluebook review attribution

`bluebook-review` retrieves the public [Bluebook Style — Epps Version](https://github.com/danepps/bluebook) at use time. Credit for that version belongs to **Professor Daniel Epps**; the upstream repository credits the original community Bluebook CSL to **Bruce D'Arcus** and **Nancy Sims**, with contributions from **Patrick O'Brien**. The upstream materials are CC BY-SA 4.0 and remain under that license. This repository is independent and is not endorsed by the upstream authors or the publishers of *The Bluebook*.

The skills use the portable `SKILL.md` folder convention and are designed for agents that support skill discovery, including OpenAI Codex and other compatible runtimes.

## Install

Clone the repository, then copy or symlink the desired skill folder into your agent's skills directory. For Codex:

```bash
git clone https://github.com/yonathanarbel/legal-ai-skills.git
mkdir -p ~/.codex/skills
cp -R legal-ai-skills/legal-bibliography ~/.codex/skills/
cp -R legal-ai-skills/inject-word-cross-references ~/.codex/skills/
cp -R legal-ai-skills/lawreview-research ~/.codex/skills/
cp -R legal-ai-skills/bluebook-review ~/.codex/skills/
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
- `bluebook-review` fetches the independently maintained [Bluebook Style — Epps Version](https://github.com/danepps/bluebook) at use time. Those upstream materials remain CC BY-SA 4.0 and are not official or exhaustive Bluebook rules.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_skills.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and testing expectations.

## License

Original repository content is Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Runtime-fetched Epps Bluebook materials retain their upstream CC BY-SA 4.0 license.
