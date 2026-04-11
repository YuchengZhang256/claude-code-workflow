# Crossref

## Overview
Crossref is the largest DOI registration agency and the authoritative source for scholarly DOI metadata — over 150 million records of journal articles, books, book chapters, conference proceedings, datasets, preprints, and more. Best for: resolving a DOI to canonical metadata, looking up references of a paper, finding journal/ISSN metadata, funder and grant lookups, and sanity-checking publication records. Crossref does not host full text — it is a metadata registry.

## Base URL
`https://api.crossref.org/`

## Authentication
No API key. Crossref operates a "polite pool" — if you include a `mailto` parameter or a `User-Agent` header with your email, your requests are routed to a faster, more reliable pool with higher rate limits. Example: `?mailto=you@example.com` or `User-Agent: MyTool/1.0 (mailto:you@example.com)`. Anonymous traffic goes to a shared pool with no guarantees.

## Key Endpoints
- `GET /works` — list/search works, filterable and sortable.
- `GET /works/<doi>` — single work by DOI (URL-encode the slash if needed, but Crossref accepts raw slashes).
- `GET /works/<doi>/agency` — which DOI registration agency owns this DOI.
- `GET /journals` — journal records.
- `GET /journals/<issn>` — single journal.
- `GET /journals/<issn>/works` — all works in a journal.
- `GET /members` — Crossref member publishers.
- `GET /members/<id>/works` — works by a specific publisher.
- `GET /funders`, `GET /funders/<id>/works` — funding agencies and their funded works.
- `GET /types` — list of work types (`journal-article`, `book-chapter`, etc.).

## Query Syntax
Crossref accepts both free-text search and structured filters on `/works`:
- `query=<text>` — generic relevance search.
- `query.bibliographic=<text>` — search on title/abstract/container.
- `query.title=<text>`, `query.author=<text>`, `query.container-title=<text>` — field-scoped.
- `filter=<key>:<value>,<key>:<value>` — structured filters. Common keys: `from-pub-date:2024-01-01`, `until-pub-date:2024-12-31`, `has-full-text:true`, `has-references:true`, `type:journal-article`, `issn:0028-0836`, `funder:10.13039/100000001`, `orcid:0000-...`.
- Sorting: `sort=issued|published|deposited|relevance&order=asc|desc`.
- `select=DOI,title,author,issued` — slim the response.
- Pagination: `rows=<1-1000>` with `offset=<n>` (max offset 10000), OR cursor pagination via `cursor=*` on first call then the returned `next-cursor`.

Examples:
- `https://api.crossref.org/works?query.bibliographic=graph+neural+network&filter=from-pub-date:2024-01-01,type:journal-article&rows=20&mailto=you@example.com`
- `https://api.crossref.org/works/10.1038/nature12373?mailto=you@example.com`
- `https://api.crossref.org/journals/0028-0836/works?rows=5`

## Response Format
JSON. Top-level envelope: `{ status, message-type, message-version, message: {...} }`. For list endpoints, `message` has `total-results`, `items-per-page`, `query`, `items: [...]`, `next-cursor`. Each item has `DOI`, `title: [...]`, `author: [ { given, family, ORCID } ]`, `issued.date-parts`, `container-title`, `publisher`, `type`, `reference-count`, `is-referenced-by-count`, `abstract` (XML-wrapped JATS when present), `reference: [...]`, `funder: [...]`, `license: [...]`, `link: [...]`.

## Rate Limits
Anonymous pool: no hard rate cap but shared throttling; expect ~5 req/sec sustained and intermittent 429s. Polite pool (with `mailto`): roughly 2x the headroom and prioritized queuing — Crossref documents this informally but the boundary is elastic. Honor the `X-Rate-Limit-Limit` / `X-Rate-Limit-Interval` response headers when present. On 429, back off and retry.

## Common Pitfalls
- `title` is an array of strings, not a string — always `item.title[0]`.
- `issued.date-parts` is `[[year, month, day]]` (a list of lists). Paper may only specify year.
- `abstract` is optional and, when present, is a JATS XML fragment — strip tags or parse it.
- Crossref counts *incoming* citations as `is-referenced-by-count` — it is a lower bound because Crossref only sees DOIs that other Crossref members have deposited as references.
- `filter` values must be comma-separated — commas inside a single value must be URL-encoded as `%2C`.
- `offset` is capped at 10000. For deep crawling, use `cursor=*` instead.
- The `query` parameter ignores Boolean operators — it is a relevance-scored bag-of-words.

## Example curl
```bash
# Lookup a DOI
curl -s 'https://api.crossref.org/works/10.1038/nature12373?mailto=you@example.com'

# Bibliographic search, 2024 journal articles only
curl -s 'https://api.crossref.org/works?query.bibliographic=causal+inference&filter=from-pub-date:2024-01-01,type:journal-article&rows=20&mailto=you@example.com'

# All works by a funder, via cursor
curl -s 'https://api.crossref.org/works?filter=funder:10.13039/100000001&rows=500&cursor=*&mailto=you@example.com'
```
