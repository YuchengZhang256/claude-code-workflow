---
name: web-access
description: "Fetch web pages that built-in WebFetch / WebSearch cannot read — Cloudflare or PerimeterX walls, JS-rendered SPAs, paywalled or login-gated content, sites that block by geo/TLS fingerprint, 403/429/503 endpoints. Use whenever WebFetch returns an error, empty body, CAPTCHA / challenge stub, 'please enable JavaScript' page, or obviously-truncated content. Primary entry point: scripts/fetch.sh <url>, which runs a Jina Reader → stealth curl → Wayback Machine fallback chain biased by per-domain hints from references/site-patterns/. For multi-URL research fanout, use scripts/fetch-parallel.sh which runs N independent fetches concurrently and emits a manifest. If the URL points to a PDF, the script exits with code 2 and defers to your PDF-extraction tool. For login-gated or interaction-heavy pages, escalate to the chrome-devtools MCP tools."
allowed-tools: Bash, Read, WebFetch, mcp__chrome-devtools__navigate_page, mcp__chrome-devtools__new_page, mcp__chrome-devtools__take_snapshot, mcp__chrome-devtools__evaluate_script, mcp__chrome-devtools__wait_for, mcp__chrome-devtools__list_pages, mcp__chrome-devtools__select_page
---

# web-access — robust web page fetcher

Built-in `WebFetch` / `WebSearch` fail on a meaningful fraction of real-world
URLs: Cloudflare challenges, bot walls, JS-rendered SPAs, sites with geo / TLS
fingerprinting, paywalls, login gates. This skill provides a layered fallback
chain so Claude can still retrieve usable content.

## When to trigger

Use this skill when `WebFetch` returns any of:

- 403 / 429 / 503 status
- empty body
- a "please enable JavaScript" / "checking your browser" stub
- a CAPTCHA or challenge screen
- obviously-truncated content (far shorter than the page should be)
- unrendered SPA HTML (React / Vue / Next.js / etc.)

Or when the user explicitly says WebFetch didn't work, or asks to "properly" /
"actually" read a URL.

**Do NOT use this skill when:**

- `WebFetch` already returned the content — it is faster and cheaper.
- The URL is a **PDF** — hand it to a dedicated PDF-extraction tool
  (`pdftotext`, `pdfplumber`, or an LLM-based extractor). `scripts/fetch.sh`
  detects PDFs and exits 2 on purpose.
- The task is performance testing, Core Web Vitals, network tracing, or
  accessibility audits — use the dedicated `chrome-devtools` skill.
- The task is academic paper search — use a paper-lookup skill.

## Coordination with other skills (important)

| Situation | Correct skill |
|---|---|
| Local PDF or image file | Dedicated PDF/image extractor |
| **Remote** PDF URL | Download with curl, then PDF extractor — **not** this skill |
| HTML page blocked by anti-bot | **this skill** |
| Page needs login session / multi-step interaction | **this skill** (Layer 4: chrome-devtools MCP) |
| Browser performance testing / Core Web Vitals | `chrome-devtools` skill |
| Search academic papers (arXiv, PubMed, Semantic Scholar) | paper-lookup skill |

`scripts/fetch.sh` refuses PDF URLs on purpose and exits with code 2 so that
routing to a PDF extractor is explicit, not implicit. Detection uses (a) a
case-insensitive URL-pattern match, then (b) a 6-second HEAD probe for
`Content-Type: application/pdf`. These cover the common cases; if both miss
(e.g. a server that blocks HEAD and serves a PDF under an HTML-looking path),
Layer 1 (Jina Reader) may still extract PDF content before you notice. When
you suspect a remote PDF and want certainty, run `curl -sI <url>` manually
first, or download the file and extract it directly.

---

## Primary entry point — `scripts/fetch.sh`

One command handles 90% of cases. It wraps the full fallback chain.

```bash
bash ~/.claude/skills/web-access/scripts/fetch.sh "https://target.site/page"
```

**Exit codes:**

| Code | Meaning | Next step |
|---|---|---|
| `0` | Success. Content is on stdout. | Read stdout. |
| `1` | Usage error (no URL given). | Fix the invocation. |
| `2` | URL is a PDF. | Download and extract with your PDF tool. |
| `3` | All layers failed. | Escalate to Layer 4 (chrome-devtools MCP). |

**Stdout:** cleaned page content — markdown when Layer 1 (Jina) succeeds,
else HTML passed through `pandoc` or `html2text.py`.
**Stderr:** per-layer progress logs (`[web-access] Layer 1: Jina Reader` etc.)
so you can see which layer produced the output.

**Typical invocation (captures output, inspects exit):**

```bash
OUT=$(bash ~/.claude/skills/web-access/scripts/fetch.sh "$URL")
rc=$?
case $rc in
  0) echo "$OUT" | head -c 20000 ;;             # feed to Claude
  2) echo "PDF — use a dedicated extractor instead" ;;
  3) echo "Escalate to chrome-devtools MCP" ;;
esac
```

---

## Parallel fanout — `scripts/fetch-parallel.sh`

For research fanout (N independent URLs), use the parallel wrapper instead
of looping `fetch.sh` serially:

```bash
bash ~/.claude/skills/web-access/scripts/fetch-parallel.sh -P 4 \
  "https://site-a/page" \
  "https://site-b/page" \
  "https://site-c/page"

# Or pipe URLs in from stdin (one per line):
cat urls.txt | bash ~/.claude/skills/web-access/scripts/fetch-parallel.sh -P 4 -
```

**Options:**

- `-P N` — max concurrent fetches (default 4). Keep modest: Jina Reader is
  rate-limited, `curl-impersonate` is CPU-heavy.
- `-o DIR` — output directory (defaults to a fresh `mktemp` dir).

**Output** (stdout, TSV): `idx<TAB>exit_code<TAB>url<TAB>content_file`,
sorted by input order. Per-URL exit codes are preserved verbatim from
`fetch.sh` — route rc=2 rows to a PDF extractor, rc=3 rows to chrome-
devtools MCP. The wrapper itself exits 0 if every URL was dispatched.

This is cheaper than spawning parallel subagents for pure URL fanout:
shared-nothing processes that only touch the filesystem.

---

## Per-domain hints — `references/site-patterns/`

Every time you discover that a specific site needs a particular header /
CSS selector / layer order to fetch cleanly, capture it in
`references/site-patterns/<host>.conf` so future fetches benefit
automatically.

Lookup order: exact host, then host with leading `www.` stripped.
Filenames are sanitized (`^[a-z0-9.-]+$`); files are shell-sourced, so
keep them to simple `KEY=value` assignments.

**Recognized variables:**

| Variable               | Purpose                                         |
|------------------------|-------------------------------------------------|
| `PREFER_LAYER`         | `jina` / `stealth` / `wayback` — tried first.   |
| `SKIP_LAYERS`          | Space-separated layers to skip entirely.        |
| `JINA_WAIT_FOR`        | CSS selector → `X-Wait-For-Selector` header.    |
| `JINA_TARGET_SELECTOR` | CSS selector → `X-Target-Selector` header.      |
| `JINA_TIMEOUT`         | Integer seconds → `X-Timeout` header.           |
| `STEALTH_REFERER`      | `Referer:` header for the stealth-curl layer.   |
| `STEALTH_EXTRA`        | Newline-separated extra header lines.           |
| `NOTES`                | Free text echoed to stderr at fetch time.       |

See `references/site-patterns/README.md` for the full spec and
`_template.conf` for a copy-ready starting point.

**When to add a pattern:** after a tricky fetch succeeds, ask what made it
work. If the answer is "a specific selector / referer / layer", capture
it. If "nothing special", do not — avoid clutter.

---

## The fallback chain

### Layer 1 — Jina Reader (primary)

[Jina Reader](https://jina.ai/reader) prefixes the target URL with
`https://r.jina.ai/` and runs it through a real headless browser server-side,
returning clean Markdown. Bypasses most Cloudflare / bot walls and handles JS
rendering. **No API key required** for basic use.

```bash
curl -sL --max-time 45 \
  -H "X-Return-Format: markdown" \
  "https://r.jina.ai/https://target.site/page"
```

**Useful request headers** (optional, add only when needed):

| Header | Effect |
|---|---|
| `X-Return-Format: markdown` | Clean markdown (default, recommended) |
| `X-Return-Format: text` | Plain text, smaller |
| `X-Return-Format: screenshot` | PNG screenshot of the rendered page |
| `X-Return-Format: html` | Raw rendered HTML |
| `X-Wait-For-Selector: <css>` | Wait for an element before capturing (lazy-loaded SPAs) |
| `X-Target-Selector: <css>` | Extract only the subtree matching the selector |
| `X-Timeout: <seconds>` | Override the default navigation timeout |

**Search alternative to WebSearch** — same idea, search endpoint:

```bash
curl -sL --max-time 45 "https://s.jina.ai/your+search+query"
```

Returns the top results as a single clean markdown document.

**Rate limits:** the free anonymous tier is generous but rate-limited; exact
quotas are documented at `jina.ai/reader`. Treat HTTP 429 as "back off
10–30 s, then retry once; if still limited, switch layers".

### Layer 2 — Stealth curl

For sites that only check HTTP headers (no real JS / TLS fingerprinting).
Fast, cheap, sometimes works when Jina is rate-limited.

`scripts/fetch.sh` auto-detects `curl-impersonate`
(`brew install curl-impersonate`) and uses it when present, which also
defeats TLS / JA3 fingerprinting used by Cloudflare. If not installed, falls
back to plain `curl` with a full Chrome 131 header set.

For non-English sites you can add to the header set:

```
-H "Referer: https://www.google.com/"
-H "Accept-Language: en-US,en;q=0.9,<your-locale>"
```

### Layer 3 — Wayback Machine

Last-resort archive lookup via the public Wayback availability API.
Particularly useful for paywalled articles, deleted posts, rate-limited
pages. The script strips the Wayback toolbar by rewriting
`/web/TS/` → `/web/TSid_/`.

```bash
curl -sL "https://archive.org/wayback/available?url=$URL" \
  | jq -r '.archived_snapshots.closest.url // empty'
```

### Layer 4 — Chrome DevTools MCP (heaviest fallback)

When all three scripted layers fail (exit code `3`), or when the page clearly
needs auth cookies / multi-step interaction, use the chrome-devtools MCP
tools directly.

**Workflow:**

1. `mcp__chrome-devtools__list_pages` — check if a browser is already running.
2. `mcp__chrome-devtools__new_page` with the target URL if not.
3. `mcp__chrome-devtools__wait_for` to wait for a content selector.
4. `mcp__chrome-devtools__take_snapshot` — returns a structured DOM snapshot
   (token-efficient).
5. Or `mcp__chrome-devtools__evaluate_script` with:

```javascript
(() => {
  const main = document.querySelector('article, main, [role="main"]') || document.body;
  return main.innerText.slice(0, 50000);
})()
```

**Use Layer 4 when:**

- Page requires a logged-in session (leverages your real browser profile).
- Multi-step flow required (click "I agree", then fetch content).
- Heavy client-side rendering that Jina Reader mis-handles.
- Need to interact (form fill, scroll to trigger lazy-load).

**Do NOT use Layer 4 when Layer 1 would work** — a real browser is ~10×
slower and consumes a browser process.

**Scope overlap with the `chrome-devtools` skill:** the dedicated
`chrome-devtools` skill is for *performance / audit* workflows (Core Web
Vitals, Lighthouse, network tracing). This skill only borrows the same MCP
tools for *content retrieval*. If the user's goal is measurement, use the
other skill.

---

## Output sanity checks (already done by `fetch.sh`)

The script applies these automatically, but if you invoke a layer directly
by hand, replicate:

1. **Length check:** discard results < 150 chars (likely an error stub).
2. **Challenge markers:** grep case-insensitively for `cf-challenge`,
   `just a moment`, `checking your browser`, `please enable javascript`,
   `captcha`, `attention required`, `access denied`, `403 forbidden`,
   `error 1020`, `cloudflare ray id`. Presence → fall through to the next
   layer.
3. **Token budget:** truncate to ~20 KB before feeding back to Claude
   (`head -c 20000`).

---

## Common traps

- **Scheme is mandatory.** Jina Reader needs `https://...` in the suffix —
  do not drop it.
- **Quote the URL.** Always wrap URLs with `?` or `&` in double-quotes so
  the shell does not split them.
- **Do not percent-encode the URL** before prefixing `https://r.jina.ai/` —
  Jina accepts raw URLs as path segment.
- **Do not log in on the user's behalf.** For auth-gated pages, ask first;
  at most reuse a pre-existing browser profile via Layer 4.
- **Do not retry in a tight loop.** HTTP 429 means back off. One retry is
  plenty; switch layers after that.
- **Legal / ToS.** This skill is for reading content the user is entitled
  to access but is blocked by over-aggressive bot walls. Do not use for
  credential stuffing, mass scraping, or clear ToS violations.

---

## Quick reference

```bash
# The 95% case — one command, exit code tells you what happened
bash ~/.claude/skills/web-access/scripts/fetch.sh "$URL"

# Manual Jina Reader
curl -sL --max-time 45 -H "X-Return-Format: markdown" "https://r.jina.ai/$URL"

# Manual Jina Search (WebSearch alternative)
curl -sL --max-time 45 "https://s.jina.ai/$QUERY"

# Manual Wayback latest snapshot
curl -sL "https://archive.org/wayback/available?url=$URL" \
  | jq -r '.archived_snapshots.closest.url // empty'

# DuckDuckGo HTML interface (no JS, extra search fallback)
curl -sL --max-time 20 \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131" \
  "https://html.duckduckgo.com/html/?q=$QUERY"
```
