# Unpaywall

## Overview
Unpaywall is a database of legal open-access copies of scholarly articles — over 30 million OA full-text links harvested from publisher sites, institutional repositories, preprint servers, and PubMed Central. Best for: given a DOI, find whether a free-to-read version exists and where. Unpaywall is the canonical "is this paper open access" check and underlies many OA browser extensions. It is DOI-only: you cannot search by title or author. For title/keyword lookups, resolve to a DOI first (via Crossref or OpenAlex), then query Unpaywall.

## Base URL
`https://api.unpaywall.org/v2/`

## Authentication
No API key. BUT the API requires an email on every request as a `?email=<you@example.com>` parameter — this is how Unpaywall identifies and contacts abusers. Missing or invalid emails return `422 Unprocessable Entity`. Use a real, monitored address.

## Key Endpoints
- `GET /v2/<doi>?email=<addr>` — lookup a single DOI. Returns the full Unpaywall record including OA status and all known OA locations.
- `GET /v2/search?query=<text>&email=<addr>` — title-only search (relevance-ranked). Returns Unpaywall records. Note this is a thin title matcher, not a full search engine — expect Crossref/OpenAlex to be better for discovery.
- `GET /v2/search/doi?query=<text>&email=<addr>` — alternative title search variant.
- Database snapshot: Unpaywall publishes a monthly gzipped JSON Lines dump for offline/batch use — request access via `https://unpaywall.org/products/snapshot`.

## Query Syntax
- Single-DOI calls take the raw DOI as the path segment (raw slashes are fine: `10.1038/nature12373`). No query language.
- The `search` endpoint accepts a free-text `query` parameter matching against titles. It is not Boolean; it is a relevance match. Optional `is_oa=true|false` filter.

Examples:
- `https://api.unpaywall.org/v2/10.1038/nature12373?email=you@example.com`
- `https://api.unpaywall.org/v2/search?query=graph+neural+networks&is_oa=true&email=you@example.com`

## Response Format
JSON. Single-DOI response (abbreviated):
```json
{
  "doi": "10.1038/nature12373",
  "doi_url": "https://doi.org/10.1038/nature12373",
  "title": "...",
  "genre": "journal-article",
  "published_date": "2013-07-18",
  "year": 2013,
  "journal_name": "Nature",
  "journal_issns": "0028-0836,1476-4687",
  "publisher": "Springer Science and Business Media LLC",
  "is_oa": true,
  "oa_status": "green",
  "has_repository_copy": true,
  "best_oa_location": {
    "url": "https://...",
    "url_for_pdf": "https://.../paper.pdf",
    "host_type": "repository",
    "version": "publishedVersion",
    "license": "cc-by",
    "repository_institution": "..."
  },
  "oa_locations": [ ... ],
  "z_authors": [ { "given": "...", "family": "..." } ]
}
```

`oa_status` values: `closed`, `green` (repository), `bronze` (free on publisher site without license), `hybrid` (OA article in a subscription journal), `gold` (fully OA journal). The `best_oa_location` is Unpaywall's pick of the best version to link; `oa_locations[]` has all known OA copies.

## Rate Limits
- 100,000 requests per day per email (generous).
- No explicit per-second cap, but be polite — sustained >10 req/sec may trigger throttling.
- Bulk jobs (more than a few hundred DOIs) should use the monthly snapshot dump instead of hammering the live API.

## Common Pitfalls
- The email is required. A call without `?email=` returns 422.
- No title-based discovery substitute for a real search engine. Use Crossref's `query.bibliographic` or OpenAlex's `search` to find a DOI, then query Unpaywall.
- `is_oa: false` means "Unpaywall has no free copy", not "the paper is definitely paywalled" — sometimes a copy exists that the crawler has not yet found.
- `best_oa_location` can be `null` even when `is_oa` is `true` — defensive-code for the null.
- The `publishedVersion` is the version of record; `acceptedVersion` is the author's post-peer-review manuscript; `submittedVersion` is the pre-peer-review draft. Some disciplines accept the accepted version as a valid citable OA copy, others insist on the published version.
- Unpaywall deduplicates by DOI — preprints (bioRxiv, arXiv) are indexed under their own DOIs, not the eventual journal DOI. Use the `has_repository_copy` and `oa_locations` to find linked preprints when available.

## Example curl
```bash
# Single DOI lookup
curl -s 'https://api.unpaywall.org/v2/10.1038/nature12373?email=you@example.com'

# Title search limited to OA
curl -s 'https://api.unpaywall.org/v2/search?query=attention+is+all+you+need&is_oa=true&email=you@example.com'

# Batch shell loop (keep concurrency low)
for doi in 10.1038/nature12373 10.1126/science.aao0702; do
  curl -s "https://api.unpaywall.org/v2/${doi}?email=you@example.com"
  sleep 0.1
done
```
