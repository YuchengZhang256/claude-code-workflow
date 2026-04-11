# bioRxiv

## Overview
bioRxiv is Cold Spring Harbor Laboratory's preprint server for biology. Its public API is intentionally minimal — it supports browsing by date window or DOI lookup, but does NOT provide keyword/full-text search. Use it for: fetching the latest preprints in a date range, resolving a bioRxiv DOI to metadata, or checking whether a bioRxiv preprint has been published in a journal. For keyword search over bioRxiv content, fall back to OpenAlex or Semantic Scholar, which index bioRxiv.

## Base URL
`https://api.biorxiv.org/`

## Authentication
None. No API key, no header required. No documented rate limit, but be polite (keep it under ~1 req/sec).

## Key Endpoints
- `details/biorxiv/<interval>/<cursor>/<format>` — list preprint metadata for a date window. `<interval>` can be a date range `YYYY-MM-DD/YYYY-MM-DD`, an integer N (most recent N posts), or `Nd` (last N days). `<cursor>` is a 0-based offset; each page returns up to 100 records. `<format>` is `json` (default), `xml`, or `html`.
- `details/biorxiv/<doi>/na/json` — single-DOI lookup (pass `na` as the cursor placeholder).
- `pubs/biorxiv/<interval>/<cursor>` — preprints that have been published in a journal, with the linking journal DOI.
- `pubs/biorxiv/<doi>/na/json` — single DOI, published-version info.
- `pub/<interval>/<cursor>/<format>` — bioRxiv-only "published" rollup.
- `publisher/<publisher_prefix>/<interval>/<cursor>` — filter published preprints by publisher DOI prefix.
- `sum/m` or `sum/y` — monthly or yearly post counts.
- `usage/m/biorxiv` — abstract views, full-text views, PDF downloads.

## Query Syntax
There is no query language. Date intervals are the primary filter. Examples:
- `https://api.biorxiv.org/details/biorxiv/2024-01-01/2024-01-31/0` — all bioRxiv preprints posted in January 2024, page 1.
- `https://api.biorxiv.org/details/biorxiv/30d/0` — last 30 days.
- `https://api.biorxiv.org/details/biorxiv/10.1101/2024.01.15.575123/na/json` — one DOI.
- `https://api.biorxiv.org/pubs/biorxiv/2024-01-01/2024-06-30/0` — preprints from H1 2024 that got published.

Category filtering is available as a querystring: append `?category=neuroscience` (lowercase, underscores for spaces) to a `details` call.

## Response Format
JSON top-level:
```json
{
  "messages": [{"status": "ok", "interval": "...", "cursor": "0", "count": 100, "total": 12345}],
  "collection": [
    {"doi": "10.1101/...", "title": "...", "authors": "...", "author_corresponding": "...",
     "author_corresponding_institution": "...", "date": "2024-01-15", "version": "1",
     "type": "new results", "license": "cc_by", "category": "neuroscience",
     "jats xml path": "...", "published": "10.1038/..." | "NA", "server": "biorxiv",
     "abstract": "..."}
  ]
}
```
`pubs/` responses add `published_doi`, `published_journal`, `published_date`, and preprint→publication links.

## Rate Limits
Undocumented. Soft convention: ≤1 req/sec. The 100-records-per-page limit is firm; paginate with `cursor` (0, 100, 200, ...).

## Common Pitfalls
- No keyword search. Do not try `?q=...` — it is silently ignored.
- `cursor` is in units of records, not pages. For page 2 use `100`, page 3 use `200`.
- For single-DOI lookups, the literal string `na` must sit in the cursor slot.
- Dates reflect the version posted, not the original submission — multiple versions of one preprint appear as separate records with incrementing `version`.
- The `published` field is `"NA"` (string) when unpublished, not `null`.

## Example curl
```bash
# Last 7 days of bioRxiv neuroscience preprints
curl -s "https://api.biorxiv.org/details/biorxiv/7d/0/json?category=neuroscience"

# Lookup a single bioRxiv DOI
curl -s "https://api.biorxiv.org/details/biorxiv/10.1101/2024.01.15.575123/na/json"

# Paginate a date range
curl -s "https://api.biorxiv.org/details/biorxiv/2024-01-01/2024-01-31/0"
curl -s "https://api.biorxiv.org/details/biorxiv/2024-01-01/2024-01-31/100"
```
