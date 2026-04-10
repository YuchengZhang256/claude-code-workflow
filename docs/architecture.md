# Architecture

How the pieces in this repo fit together inside Claude Code.

## The three persistence layers

Claude Code has three orthogonal ways to give Claude persistent context.
Skills alone are not enough — the interesting behavior comes from pairing
them with the other two layers.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ~/.claude/CLAUDE.md                           │
│                                                                   │
│  HARD RULES. Injected into every turn. Overrides skill            │
│  descriptions and Claude's own judgment.                          │
│                                                                   │
│  Examples in this repo:                                           │
│    • Web-fetch escalation protocol                                │
│    • Handoff-on-startup rule                                      │
│    • Multi-model review protocol                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ~/.claude/skills/<name>/                       │
│                                                                   │
│  SOFT RULES. Loaded on-demand when description matches.           │
│  Provide specialized capabilities + scripts + templates.          │
│                                                                   │
│  Skills in this repo:                                             │
│    • web-access      — layered anti-bot web fetcher               │
│    • handoff          — session → HANDOFF.md compressor           │
│    • simplify         — changed-code self-review                  │
│    • research-wiki    — Karpathy-style persistent knowledge       │
│    • multi-model-review — adversarial cross-model review          │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│             ~/.claude/projects/<project>/memory/                   │
│                                                                   │
│  CROSS-SESSION MEMORY. Four types (user / feedback / project /    │
│  reference). MEMORY.md is an index loaded every turn.             │
│                                                                   │
│  Templates in this repo:                                           │
│    • dotclaude/memory/MEMORY.md.template                          │
│    • dotclaude/memory/user_profile.md.template                    │
│    • dotclaude/memory/feedback_example.md                         │
│    • dotclaude/memory/project_example.md                          │
└─────────────────────────────────────────────────────────────────┘
```

**Rule of thumb for where to put something**:

| Nature | Layer |
|---|---|
| "Claude MUST always do X when Y" | **CLAUDE.md** hard rule |
| "Give Claude the ability to do X on request" | **Skill** |
| "Remember this fact across conversations" | **Memory** |
| "State inside one session only" | (nowhere — use `HANDOFF.md` if it needs to survive this session end) |

## How skills trigger

Claude reads the `description` field of every installed skill at the start
of each turn, then decides whether any of them apply. **Description quality
is everything.** Write descriptions as trigger rules:

- List the exact user phrases that should activate the skill
- List the situations it should activate in
- Explicitly state when it should NOT activate (to prevent conflicts with
  other skills)

Bad description:

> "A nice skill for working with web pages."

Good description:

> "Fetch web pages that built-in WebFetch / WebSearch cannot read —
> Cloudflare or PerimeterX walls, JS-rendered SPAs, paywalled or
> login-gated content, 403/429/503 endpoints. Use whenever WebFetch
> returns an error, empty body, CAPTCHA / challenge stub, 'please enable
> JavaScript' page, or obviously-truncated content. **Do NOT use for PDF
> URLs** — defer to a PDF extractor. Do NOT use for performance testing
> — use the `chrome-devtools` skill."

## Hard vs soft rules

```
Hardness              Mechanism              Reliability
───────────────────────────────────────────────────────────
HIGHEST   CLAUDE.md               Every turn, forced injection
          global instructions     Cannot be "forgotten"
            │
            │
          Skill description       Matched at turn start
            │                     Loaded only if relevant
            │                     Can miss edge cases
            │
LOWEST    Claude's judgment       Depends on in-context
                                  reasoning this turn
                                  No guarantees
```

**Methodology**: things Claude **must** do → CLAUDE.md. Things Claude
**can** do → skill. Everything else → in-context judgment.

The `web-access` skill is a canonical example: the skill itself is
powerful, but what actually makes Claude reach for it reliably when
`WebFetch` fails is the `CLAUDE.md` hard rule. Without that rule, Claude
tends to "give up gracefully" — which is the opposite of what the user
wants.

## Cross-skill coordination

Skills can collide when two of them match the same situation. Three
strategies:

1. **Write explicit skill boundaries in each SKILL.md.** Every skill in
   this repo has a "Do NOT use when" section naming the other skills that
   own adjacent territory.
2. **Prefer narrow descriptions.** `pdf` should say "manipulation only,
   not reading" if a PDF extractor skill is also installed.
3. **Use a CLAUDE.md rule as tie-breaker.** For high-stakes collisions
   (e.g. "all PDFs go to the extractor"), write the rule in `CLAUDE.md`
   so it overrides both skills.

## How memory interacts with skills

The memory system lives *under* Claude's control — Claude decides when to
read, write, and update memory files. The four memory types serve
different purposes:

| Type | When to write | When to read |
|---|---|---|
| `user` | Learned a new fact about the user's role or preferences | Tailoring explanations, choosing abstraction level |
| `feedback` | User corrected or confirmed an approach | Before making a similar decision again |
| `project` | Learned a non-code fact about ongoing work | Before acting on requests involving that project |
| `reference` | User pointed to an external system | When a related external lookup is needed |

Memory **complements** skills: a skill gives Claude the ability to do
something; memory tells Claude whether and how to do it *for this user*.
