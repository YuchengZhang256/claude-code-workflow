# Case Study: Building `web-access` — 15 Bugs, Three Review Passes

A war story from the development of the `web-access` skill. This doc
exists because every principle in [`../philosophy.md`](../philosophy.md)
was learned the hard way here. If you are about to write your own skill,
read this first — the bugs will look familiar.

## Context

**Problem**: Claude Code's built-in `WebFetch` fails on Cloudflare-
protected sites, JS-rendered SPAs, paywalled articles, and any page with
real anti-bot hardening. "Just install a better fetcher" turns out to
involve a lot more than installing one tool.

**Goal**: a single skill with one entry point — `fetch.sh <url>` — that
runs a layered fallback chain (Jina Reader → stealth curl → Wayback
Machine → Chrome DevTools MCP) and returns usable content, with exit
codes so Claude can branch on outcome.

**Rough final size**:

- `SKILL.md`: ~210 lines
- `scripts/fetch.sh`: ~260 lines
- `scripts/html2text.py`: ~85 lines
- Total: ~550 lines

**Bug count**: 15. Distribution:

| Review method | Bugs found | Percentage |
|---|---|---|
| Self-review after v1 | 9 | 60% |
| Smoke testing | 2 | 13% |
| Adversarial review by different-family model | 4 | 27% |

Each category found a class of bug the others missed. Skipping any one
of the three would have shipped a broken skill.

---

## Phase 1 — Self-review (9 bugs)

After writing v1, I read the diff with fresh eyes. These are the bugs a
careful verifier catches on a second pass.

| # | Bug | Fix |
|---|---|---|
| 1 | `python3 -c "..."` embedded multi-line class definition → shell quoting broke it completely | Extracted into a standalone `html2text.py` |
| 2 | Hardcoded `curl_chrome131` version — Homebrew ships `curl_chrome124`, `curl_chrome116`, etc. depending on the day | Runtime glob: `for cand in /opt/homebrew/bin/curl_chrome*; do ...; done` |
| 3 | `X-With-Generated-Alt: false` — comment said "strips images", reality is "don't generate alt text for images". Misleading, and not what we wanted. | Removed the header |
| 4 | **PDF URLs silently flowed through to Jina Reader**, bypassing the global CLAUDE.md rule that says PDFs must go through a dedicated extractor | Added `is_pdf_url()` function + exit code 2 |
| 5 | No skill-boundary documentation — unclear how `web-access` should coordinate with `chrome-devtools`, PDF skills, paper lookup skills | Added a "Coordination with other skills" table to SKILL.md |
| 6 | Layer 4 originally included a Google Cache fetch — Google killed the cache feature in 2024 | Deleted the dead layer |
| 7 | Comment claimed "Jina rate limit is 20 RPM" — I had made that up | Changed to "see jina.ai/reader docs for current quotas" |
| 8 | No search-engine fallback for when WebSearch itself fails | Added DuckDuckGo HTML endpoint to the SKILL.md cheatsheet |
| 9 | All the curl logic lived inside SKILL.md markdown — Claude would have to reconstruct a 50-line command on every invocation | Extracted into `scripts/fetch.sh` |

**Lesson**: self-review catches the biggest single category of bugs, but
every bug here is something I could have predicted. None required actually
running the code.

---

## Phase 2 — Smoke testing (2 bugs)

Then I ran `fetch.sh` against `https://example.com` and
`https://httpbin.org`. Two bugs surfaced immediately — both classes of bug
no static review could have caught.

### Bug 10 — False-positive "blocked" detection

`example.com` returns a minimal but valid 328-byte page. My `is_blocked()`
check said "responses < 400 bytes are probably error stubs". The check
rejected the legitimate `example.com` content and fell through to the next
layer unnecessarily.

**Fix**: dropped the threshold to 150 bytes, which is the point below
which a page is genuinely empty rather than just compact.

### Bug 11 — The brotli / NUL-truncation bug

This one was the most educational. I requested
`Accept-Encoding: gzip, deflate, br` in the stealth curl layer. Behavior:

1. The server returned a Brotli-compressed body
2. macOS system curl (8.7.1 at the time) was **compiled without Brotli
   support**, so it didn't decode the body
3. The raw Brotli bytes contained `\0` (NUL) characters
4. My bash script captured the output with `OUT=$(curl ...)`
5. Bash variable assignment **silently truncates at the first NUL byte**
6. `$OUT` became an empty string
7. `is_blocked` correctly reported "blocked/too short"
8. We fell through to the next layer, producing the wrong fallback path

Running `curl -v` exposed `content-encoding: br` in the response headers
and obvious binary garbage in the body. None of this was visible from
reading the code.

**Fix**: runtime capability detection.

```bash
ACCEPT_ENCODING="gzip, deflate"
if [ -n "$IMPERSONATE" ]; then
  # curl-impersonate ships full chromium codec set
  ACCEPT_ENCODING="gzip, deflate, br, zstd"
elif curl --version 2>/dev/null | head -1 | grep -qi brotli; then
  ACCEPT_ENCODING="gzip, deflate, br"
fi
```

**Two lessons**:

1. Shell variables cannot hold binary data. If you capture something that
   might be binary, write it to a file first and process the file.
2. Never assume the environment has feature X. Probe for it.

---

## Phase 3 — Adversarial review (4 bugs, 3 rounds)

I attached the three files to a different-family external model (call it
"the adversary") and prompted:

> You are an adversarial code reviewer. Assume there ARE bugs. Find
> them. Be blunt.

### Round 1 — 2 real bugs

**Bug 12 — Wayback URL not percent-encoded**

```bash
curl -sL "https://archive.org/wayback/available?url=$URL"
```

If `$URL` contains an `&`, the shell sees it as a second query parameter
to the archive.org API, not as part of the URL we're asking about. The
Wayback API then looks up a truncated URL and returns the wrong snapshot
(or none).

**Fix**: `urlencode()` helper, applied to `$URL` before interpolation.

```bash
urlencode() {
  python3 -c 'import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
}
encoded=$(urlencode "$URL")
curl -sL "https://archive.org/wayback/available?url=$encoded"
```

**Bug 13 — `pipefail` + `SIGPIPE` in the challenge detector**

This one is the meanest in the whole story. My original `is_blocked`
checked for challenge-page markers like this:

```bash
printf '%s' "$text" | head -c 8192 | grep -qiE "cf-challenge|just a moment|..."
```

Which looks right. But I was running the script with `set -o pipefail`.
Here is what happens on a challenge page:

1. `printf` starts writing `$text` to the pipe
2. `head -c 8192` reads the first 8 KB
3. `grep -q` matches early in that 8 KB and exits `0`
4. `head` tries to keep writing, but the pipe is closed → `SIGPIPE`
5. `head` exits with code 141
6. `pipefail` propagates the highest non-zero exit through the pipeline
7. The whole expression ends up with exit `141`, not `0`
8. The `&& return 0` for "blocked" silently **fails to fire**
9. A challenge page passes the "is this blocked" check

This is a silent failure that exactly defeats the purpose of the check.
Every Cloudflare challenge would have fallen through to `emit_success`
instead of to the next layer.

**Fix**: eliminate the pipe entirely, use bash parameter expansion +
here-string.

```bash
local head_text="${text:0:8192}"
if grep -qiE "cf-challenge|just a moment|..." <<< "$head_text"; then
  return 0
fi
```

**Lesson**: `pipefail` + `SIGPIPE` is one of the most subtle corners of
shell programming. The fact that an adversarial model from a different
family caught this and I did not is exactly why the protocol exists.

### Round 2 — 2 more real bugs

**Bug 14 — Case-sensitive PDF detection**

```bash
[[ "$URL" =~ \.pdf($|[?#]) ]]
```

This matches `.pdf` but not `.PDF`, `.Pdf`, etc. Real-world URLs include
all of these — `https://example.com/paper.PDF` would slip through
unnoticed, get sent to Jina Reader, and Jina would extract the PDF
content, directly violating the global CLAUDE.md rule.

**Fix**:

```bash
shopt -s nocasematch
if [[ "$URL" =~ \.pdf([?#]|$) ]]; then matched=1
elif [[ "$URL" =~ arxiv\.org/pdf/ ]]; then matched=1
elif [[ "$URL" =~ (bio|med)rxiv\.org/.*\.full\.pdf ]]; then matched=1
fi
shopt -u nocasematch
```

**Bug 15 — A comment that described a bug as acceptable**

My original code had a comment saying:

> "If the PDF detection misses (no extension, no content-type header),
> the URL flows through to Jina Reader. Sub-optimal but not broken."

The adversary pointed out: **this is broken**. "Jina Reader will extract
the PDF content" is exactly the outcome the global CLAUDE.md rule
forbids. There is no "sub-optimal but not broken" here — the PDF
extraction global rule has no exception.

**Fix**: added a HEAD probe as a second detection path (Content-Type
check), and documented the remaining corner case (servers that block
HEAD *and* serve PDFs under HTML-looking paths) explicitly in SKILL.md
as a "residual gap" so the caller can intervene.

This wasn't a code bug. It was a judgment error — I had accepted a
correctness gap as acceptable when it wasn't. That is exactly the kind
of blind spot self-review cannot catch, because self-review uses the
same judgment that introduced the gap.

### Round 3 — No new findings → SHIP

---

## Attribution summary

```
                 Self-review   Smoke test   Adversarial
Bugs found:          9             2            4
Percentage:         60%           13%          27%

Bug character:
  Self-review:     Predictable logic errors, dead code, skill boundaries
  Smoke test:      Environment assumptions, binary-in-shell-variable
  Adversarial:     Shell gotchas (pipefail+SIGPIPE), encoding edge cases,
                   judgment errors about acceptable gaps
```

**No single review method covers the full space.** The three are
complementary:

- **Self-review** is the highest-yield but chronically over-confident
  (you trust the code you just wrote)
- **Smoke test** is the only path to environment-assumption bugs
- **Adversarial review** catches the bugs where the code *looks* right
  but has a subtle semantic failure

## Takeaways

1. **Ship nothing until all three review methods have run.** If any one
   of them has not been tried, there is a measurable, known distribution
   of bugs still in the code.
2. **Adversarial review uses a different model family**. Same-family
   adversaries share blind spots; the 27% is only the 27% when the
   reviewer is not a sibling of the verifier.
3. **Arbitrate adversarial findings** — about 30% are false positives.
   Blindly applying them introduces new bugs.
4. **Judgment errors are real bugs**. "Acceptable sub-optimality" is how
   correctness gaps ship. An adversary has no investment in your
   original framing and will call them out.
5. **Smoke-test the first run**, not the tenth. The first run is
   development, not QA.
6. **The `scripts/` subdirectory is not optional** — most of the bugs in
   this list (2, 11, 12, 13) would have been harder to find if the logic
   had stayed inside SKILL.md markdown.

---

## See also

- [`../philosophy.md`](../philosophy.md) — the seven principles
  distilled from this story
- [`../skill-authoring-guide.md`](../skill-authoring-guide.md) — the
  methodology as a reusable recipe
- [`../multi-model-review.md`](../multi-model-review.md) — the
  adversarial review protocol in detail
- [`../../skills/web-access/`](../../skills/web-access/) — the final
  skill, after all 15 fixes
