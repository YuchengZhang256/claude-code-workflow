# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release.
- `skills/web-access` — layered web fetcher (Jina Reader → stealth curl → Wayback → Chrome DevTools MCP).
- `skills/handoff` — session-to-`HANDOFF.md` compressor.
- `skills/simplify` — changed-code self-review skill.
- `skills/research-wiki` — Karpathy-style persistent knowledge wiki operator.
- `skills/multi-model-review` — adversarial review protocol (verifier → stress-tester → arbitrator).
- `dotclaude/CLAUDE.md.template` — global hard rules template.
- `dotclaude/memory/` — four memory-type templates (user / feedback / project / reference).
- `examples/research-wiki-starter/` — clone-per-domain wiki skeleton.
- `scripts/install.sh` — dry-run-by-default installer.
- `docs/` — architecture, philosophy, quickstart, case studies.
