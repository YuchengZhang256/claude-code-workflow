# medRxiv

## Overview
medRxiv is the Cold Spring Harbor Laboratory / BMJ / Yale preprint server for health sciences (medicine, clinical research, public health, epidemiology). It shares its API infrastructure with bioRxiv — same endpoints, same response format, same caveats. The only difference is the `server` path segment. As with bioRxiv, there is no keyword search; use OpenAlex or Semantic Scholar for text queries over medRxiv content.

## Base URL
`https://api.biorxiv.org/`  (shared host — the server segment in the path determines medRxiv vs bioRxiv)

## Authentication
None. No API key. No documented rate limit. Be polite (≤1 req/sec).

## Key Endpoints
- `details/medrxiv/<interval>/<cursor>/<format>` — list medRxiv preprint metadata for a date window. `<interval>` is `YYYY-MM-DD/YYYY-MM-DD`, integer N, or `Nd`. `<cursor>` is a 0-based offset in 100-record pages. `<format>` is `json` (default), `xml`, or `html`.
- `details/medrxiv/<doi>/na/json` — single-DOI lookup.
- `pubs/medrxiv/<interval>/<cursor>` — medRxiv preprints that have been published in a journal.
- `pubs/medrxiv/<doi>/na/json` — single DOI, published-version info.
- `publisher/<publisher_prefix>/<interval>/<cursor>` — filter by publisher DOI prefix.
- `sum/m` / `sum/y` — aggregate post counts (shared with bioRxiv).
- `usage/m/medrxiv` — monthly usage stats.

## Query Syntax
No query language — filter by date window and optionally a category via `?category=<name>`. medRxiv category slugs are lowercase with underscores (e.g., `infectious_diseases`, `public_and_global_health`, `epidemiology`). Examples:
- `https://api.biorxiv.org/details/medrxiv/2024-03-01/2024-03-31/0`
- `https://api.biorxiv.org/details/medrxiv/14d/0/json?category=infectious_diseases`
- `https://api.biorxiv.org/details/medrxiv/10.1101/2024.03.10.24304012/na/json`

## Response Format
Identical to bioRxiv. JSON top-level `messages[]` + `collection[]`. Each record has `doi`, `title`, `authors`, `author_corresponding`, `author_corresponding_institution`, `date`, `version`, `type`, `license`, `category`, `jats xml path`, `abstract`, `published` (DOI string or `"NA"`), and `server: "medrxiv"`. The `pubs/` variant adds `published_doi`, `published_journal`, `published_date`.

## Rate Limits
Same as bioRxiv — no hard cap documented; keep it under ~1 req/sec. Paginate with `cursor` in increments of 100.

## Common Pitfalls
- No full-text or keyword search. `?q=...` does nothing.
- The `server` must be spelled exactly `medrxiv` (lowercase, no hyphen).
- Shared host with bioRxiv — mixing up `biorxiv` and `medrxiv` in the path returns the wrong dataset silently.
- Version bumps appear as separate rows; if you only want the latest, dedupe by DOI and take the max `version`.
- medRxiv has a manuscript screening step that adds delay — records may lag 1–2 days behind posting.
- For COVID-19 era analyses, note that many medRxiv papers carry a disclaimer about clinical practice implications — downstream consumers should preserve that signal.

## Example curl
```bash
# Last 14 days of medRxiv
curl -s "https://api.biorxiv.org/details/medrxiv/14d/0/json"

# Single DOI lookup
curl -s "https://api.biorxiv.org/details/medrxiv/10.1101/2024.03.10.24304012/na/json"

# Paginate a wider window
curl -s "https://api.biorxiv.org/details/medrxiv/2024-01-01/2024-06-30/0"
curl -s "https://api.biorxiv.org/details/medrxiv/2024-01-01/2024-06-30/100"

# Check published-in-journal status for an interval
curl -s "https://api.biorxiv.org/pubs/medrxiv/2024-01-01/2024-03-31/0"
```
