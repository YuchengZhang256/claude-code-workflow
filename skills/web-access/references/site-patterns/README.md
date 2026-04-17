# site-patterns

Per-domain hints that `fetch.sh` consults to bias the fallback chain.
The goal is institutional memory: every time you discover that a given site
needs a particular header / selector / layer order, drop it here so future
fetches benefit automatically.

## File layout

```
references/site-patterns/
  <host>.conf       # shell-sourced, machine-readable hints (REQUIRED to be picked up)
  <host>.md         # optional human notes (free text, ignored by fetch.sh)
```

`<host>` is the lowercased hostname. Lookup tries the exact host first, then
the same host with a leading `www.` stripped. There is **no TLD walking** —
write `arxiv.org.conf`, not `org.conf`.

Filenames are sanitized (`^[a-z0-9.-]+$`). Anything else is rejected.

## Recognized variables (`<host>.conf`)

| Variable               | Purpose                                                          |
|------------------------|------------------------------------------------------------------|
| `PREFER_LAYER`         | One of `jina` / `stealth` / `wayback`. Tried first.              |
| `SKIP_LAYERS`          | Space-separated layers to skip entirely.                         |
| `JINA_WAIT_FOR`        | CSS selector → Jina `X-Wait-For-Selector` header.                |
| `JINA_TARGET_SELECTOR` | CSS selector → Jina `X-Target-Selector` header (extract subtree).|
| `JINA_TIMEOUT`         | Integer seconds → Jina `X-Timeout` header.                       |
| `STEALTH_REFERER`      | Sets `Referer:` for the stealth-curl layer.                      |
| `STEALTH_EXTRA`        | Newline-separated extra header lines for stealth curl.           |
| `NOTES`                | Free text echoed to stderr at fetch time.                        |

The `.conf` file is **sourced by bash**, not parsed. Keep it to plain
`KEY=value` assignments. Anything you put in there runs with your shell
permissions; do not paste files from untrusted sources.

## How to grow this directory

1. After a tricky fetch succeeded, ask: *what made it work that wouldn't
   apply to a generic page?*
2. If the answer is "a specific selector / referer / layer", capture it
   here. If it's "nothing special", do not.
3. Prefer the smallest hint that works. `JINA_WAIT_FOR` alone is often
   enough; you rarely need both `PREFER_LAYER` and `SKIP_LAYERS`.
4. Update `NOTES` with the date and what broke before. Future-you will
   thank present-you.

## Example: a JS-heavy article site

`example-news.com.conf`

```sh
JINA_WAIT_FOR='article'
JINA_TARGET_SELECTOR='article'
JINA_TIMEOUT='30'
NOTES='lazy-loaded article body, plain stealth curl returns the SPA shell only.'
```

## Example: a site that geo-blocks by IP

`some-site.com.conf`

```sh
PREFER_LAYER='jina'
SKIP_LAYERS='stealth'
NOTES='stealth curl from a non-local IP gets a 403 page; Jina rendering server routes through a supported region and works.'
```
