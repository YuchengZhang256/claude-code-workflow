# Quickstart

Ten minutes from clone to working workflow.

## Prerequisites

- Claude Code CLI installed and working (`claude` command available)
- `bash`, `curl`, `python3`, `git` (standard on macOS / most Linux)
- Optional but recommended: `pandoc`, `jq`, `curl-impersonate`

Check with `scripts/sanity-check.sh` after installing.

## 1. Clone

```bash
git clone https://github.com/<your-fork>/claude-code-workflow.git
cd claude-code-workflow
```

## 2. Dry-run the installer

The installer defaults to **dry-run** — it prints what it would do without
touching `~/.claude/`:

```bash
./scripts/install.sh
```

Read the output carefully. Anything under `~/.claude/` that already exists
will be listed with a "`[skip — already exists]`" note; the installer
does not overwrite.

## 3. Apply

```bash
./scripts/install.sh --apply
```

This:

- Copies `skills/*` into `~/.claude/skills/` (skipping ones that already
  exist)
- Copies `dotclaude/CLAUDE.md.template` into `~/.claude/CLAUDE.md` **only
  if no file is already there** — otherwise prints a merge-by-hand hint
- Sets the executable bit on all `scripts/*.sh` inside each skill

**Memory templates are NOT copied automatically**, because Claude Code
memory is project-scoped (`~/.claude/projects/<project>/memory/`) and
the installer cannot safely guess which project you want them under.
Copy them by hand into your project's memory directory when ready:

```bash
# After a Claude Code session has created ~/.claude/projects/<project>/
cp dotclaude/memory/*.md.template \
   dotclaude/memory/*_example.md \
   ~/.claude/projects/<project>/memory/
```

## 4. Verify

```bash
./scripts/sanity-check.sh
```

Expected output:

```
✓ bash       (Bash ... )
✓ curl       (curl ... )
✓ python3    (Python ... )
✓ git        (git version ... )
~ pandoc     (optional, not found — web-access still works)
~ jq         (optional, not found — web-access falls back to python)
~ curl-impersonate (optional, not found — install via brew)

Skills installed at ~/.claude/skills/:
  ✓ web-access
  ✓ handoff
  ✓ simplify
  ✓ research-wiki
  ✓ multi-model-review

Global rules:
  ✓ ~/.claude/CLAUDE.md present
```

## 5. Smoke-test web-access

```bash
bash ~/.claude/skills/web-access/scripts/fetch.sh "https://example.com"
```

You should see on stderr:

```
[web-access] Layer 1: Jina Reader
[web-access]   ✓ success via jina (... raw bytes)
```

And on stdout, the cleaned markdown body of `example.com`.

## 6. Fill in `~/.claude/CLAUDE.md`

Open `~/.claude/CLAUDE.md` and customize the top section:

- Your role / domain / language preference
- Any personal rules you want to add

The rest of the file (session continuity, web-fetch escalation, multi-model
review protocol, etc.) can stay as-is.

## 7. Bootstrap your first research wiki (optional)

```bash
bash ~/.claude/skills/research-wiki/scripts/new-wiki.sh \
    ~/research/my-first-wiki "my domain"
```

Then drop a paper into `~/research/my-first-wiki/raw/` and tell Claude:

> ingest raw/<paper-filename>

Claude reads the per-wiki `CLAUDE.md`, runs the ingest protocol, and
commits the first wiki pages.

## 8. End your first session with `/handoff`

Before closing a session that matters:

> /handoff

Claude writes `HANDOFF.md` in the current directory. Next time you open
Claude Code in the same directory, it reads the file automatically (per
the `CLAUDE.md` hard rule) and resumes with full context.

## That's it

For deeper dives:

- [`architecture.md`](./architecture.md) — how the three persistence
  layers interact
- [`philosophy.md`](./philosophy.md) — the seven methodology principles
- [`skill-authoring-guide.md`](./skill-authoring-guide.md) — writing your
  own skills
- [`research-wiki-guide.md`](./research-wiki-guide.md) — the Karpathy-style
  wiki workflow in detail
- [`multi-model-review.md`](./multi-model-review.md) — adversarial review
  protocol
