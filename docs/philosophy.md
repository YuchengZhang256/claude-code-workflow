# Philosophy

Seven principles that shape every skill and rule in this repo. Read this
before authoring your own extensions — the implementation details change,
but the methodology compounds.

## 1. Build your own skill when the built-in is too weak

`WebFetch` fails on Cloudflare, SPAs, and paywalls. Complaining about that
takes five seconds. Building `web-access` — a skill that actually solves
it — takes an afternoon. The afternoon returns 100× the value over a
year of use.

**Corollary**: the set of things Claude Code *can* do is not the set of
things the built-ins do. It is the set of things your `~/.claude/skills/`
directory does, which is whatever you put in it.

## 2. Skills get a `scripts/` subdirectory

Putting 200 lines of bash inside `SKILL.md` markdown forces Claude to
copy-paste long commands every time the skill fires. That is slow, error
prone, and opaque.

Extract everything longer than a few lines into a script under `scripts/`,
and have `SKILL.md` invoke it with parameters:

```bash
bash ~/.claude/skills/my-skill/scripts/run.sh "$ARG"
```

Benefits:

- `SKILL.md` stays short and focused on *when* to use the skill
- The script is directly testable from the shell (and from smoke tests)
- Bug fixes live in one place
- Claude's prompts get smaller

## 3. Multi-layer fallback beats single-point hardening

A scraper using only Playwright is slower than Jina Reader on 80% of
pages and still fails on the remaining 20%. A single-point solution
optimizes for one failure mode at the cost of everything else.

Layered fallback — each layer cheap, each layer covering a different
failure mode — dominates:

```
Jina Reader     →  headless browser as a service (fast, generic)
Stealth curl    →  defeats header / TLS fingerprinting  (fast, narrow)
Wayback         →  snapshots of dead or paywalled pages (slow, unusual)
Chrome DevTools →  real browser with user cookies       (slowest, auth)
```

**Corollary**: each layer should report its failure cleanly so the caller
knows which layer to try next. Use exit codes and stderr logs, not
English-sentence errors.

## 4. Skill descriptions must include explicit boundaries

Two skills whose descriptions both fire on "read this PDF" will collide.
Claude picks one semi-randomly, you get inconsistent behavior, and you
blame the model.

Fix: every `SKILL.md` lists the adjacent skills and says which one owns
which territory. `web-access` in this repo has a coordination table:

| Situation | Correct skill |
|---|---|
| Local PDF | PDF extractor |
| Remote PDF URL | Download → PDF extractor |
| HTML blocked by anti-bot | web-access |
| Browser performance test | chrome-devtools |

Without that table, `web-access`, `pdf`, and `chrome-devtools` would
fight over the same triggers.

## 5. Smoke-test before declaring done

Static review finds the bugs you can predict. Running the code finds the
bugs you couldn't predict — often because they live in environment
assumptions rather than in the code itself.

Real example from the `web-access` skill: macOS system curl 8.7.1 is
built without Brotli support. Asking for `Accept-Encoding: br` returned
the raw compressed bytes, which included NUL characters, which silently
truncated when assigned to a bash variable. No amount of reading the
code could have caught this — only running it against `example.com`.

**Rule**: the first run is part of development, not deployment.

## 6. Adversarial review across model families catches the last 27%

Different models have different blind spots. The verifier model (the one
that wrote the code, or the one doing first-pass review) will miss a
specific class of bugs that an adversarial model from a different family
reliably catches.

Attribution from the `web-access` skill development (see
[case-studies/web-access-15-bugs.md](./case-studies/web-access-15-bugs.md)):

```
                Self-review   Smoke test   Adversarial review
Bugs found:          9             2               4
Percentage:         60%           13%             27%
```

The 27% from adversarial review were the hardest bugs — shell `pipefail`
+ `SIGPIPE` interaction, case-sensitive regex when case-insensitive was
required, un-percent-encoded URL parameters. These were not caught by
our self-review or smoke tests, and only surfaced once an adversarial
model from a different family looked at the same code.

See [multi-model-review.md](./multi-model-review.md) for the full
protocol.

## 7. Hard rules go in `CLAUDE.md`

Skill descriptions are soft matches — they fire when Claude thinks they
apply. If Claude misjudges the situation (common for ambiguous cases),
the skill doesn't fire and the user gets default behavior.

If a rule needs to hold **always**, put it in `~/.claude/CLAUDE.md`. That
file is injected into every turn unconditionally. It is the only reliable
mechanism for hard constraints.

In this repo:

- Web-fetch escalation is a CLAUDE.md rule (not a skill description)
  because "WebFetch returned 403, now escalate" must not be a judgment
  call.
- Handoff-on-startup is a CLAUDE.md rule because "read `HANDOFF.md` if
  it exists" must not be skipped.
- PDF extraction routing is a CLAUDE.md rule because multiple skills
  claim adjacent territory.

---

## Summary

Tools change, methodology compounds. The seven principles above apply to
any future skill you write, on any future version of Claude Code, with
any future set of built-in tools. They are the only durable part of this
repo.
