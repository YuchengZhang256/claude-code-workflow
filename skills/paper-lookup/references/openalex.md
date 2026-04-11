# OpenAlex

## Overview
OpenAlex is a free, open catalog of the global research system — over 250 million works, plus authors, institutions, sources (journals/repositories), concepts/topics, publishers, and funders, all interlinked. It is the successor to Microsoft Academic Graph. Best for: broad multidisciplinary search, citation graph exploration, author disambiguation, institutional analytics, and anything where you need JSON (unlike Crossref which is DOI-metadata-only and arXiv which is preprint-only). Coverage spans biomedical, physical, social sciences, and humanities.

## Base URL
`https://api.openalex.org/`

## Authentication
No API key is required for the standard (non-premium) API. To enter the "polite pool" (higher priority, better reliability), include your email in every request — either as `?mailto=you@example.com` or in the `User-Agent` header (`User-Agent: MyTool/1.0 (mailto:you@example.com)`). OpenAlex also offers a paid premium tier with a bearer API key for higher throughput and SLA — set `Authorization: Bearer <key>` if you have one, but most workflows do not need it.

## Key Endpoints
- `GET /works` — list/search works (papers, books, datasets, preprints).
- `GET /works/<id>` — single work; `<id>` can be an OpenAlex ID (`W2741809807`), a DOI (`https://doi.org/10.7717/peerj.4375` or `doi:10.7717/peerj.4375`), a PMID (`pmid:14907713`), or an arXiv ID (`arxiv:2103.15348`).
- `GET /authors`, `GET /authors/<id>` — authors (IDs like `A5062108845`, or `orcid:0000-...`).
- `GET /sources`, `GET /sources/<id>` — journals, conferences, repositories (e.g., `S137773608`).
- `GET /institutions`, `GET /institutions/<id>` — ROR-backed institutions.
- `GET /topics`, `GET /concepts`, `GET /publishers`, `GET /funders` — taxonomy and organization entities.
- `GET /works?filter=...&group_by=<field>` — facet aggregations.

## Query Syntax
Two orthogonal parameters:
- `search=<text>` — full-text relevance search across title/abstract/fulltext. Use `title.search`, `abstract.search`, `title_and_abstract.search`, or `fulltext.search` as filters for field-specific matching.
- `filter=<key>:<val>,<key>:<val>` — structured filters. Commas mean AND. Use `|` inside a value for OR. Common keys:
  - `publication_year:2023` or `from_publication_date:2023-01-01,to_publication_date:2023-12-31`
  - `is_oa:true`
  - `type:journal-article` (or `preprint`, `review`, `book-chapter`)
  - `cited_by_count:>100`
  - `authorships.author.id:A5062108845`
  - `authorships.institutions.ror:https://ror.org/...`
  - `concepts.id:C41008148` (concept: computer science)
  - `primary_topic.id:T10017`
  - `best_oa_location.license:cc-by`

Pagination: `per_page=<1-200>` plus either `page=<n>` (max 10k results total) or `cursor=*` (first call) then the returned `next_cursor` (unlimited). Use cursor pagination for any serious crawl.

Select fields with `select=id,title,doi,publication_year` to slim the response.

## Response Format
JSON. List endpoints return `{ meta: { count, db_response_time_ms, page, per_page, next_cursor }, results: [...], group_by: [...] }`. Each work object includes `id`, `doi`, `title`, `display_name`, `publication_year`, `publication_date`, `type`, `cited_by_count`, `authorships[]` (with `author.id`, `author.display_name`, `institutions[]`), `concepts[]`, `topics[]`, `primary_topic`, `open_access` (status, url), `locations[]`, `best_oa_location`, `referenced_works[]`, `related_works[]`, `abstract_inverted_index` (reconstruct with a helper — OpenAlex does not ship plain abstract text for licensing reasons).

## Rate Limits
Polite pool: 10 requests/sec and 100,000 calls/day per user. Anonymous pool: shared quota, lower priority, no SLA. Premium tier: higher limits per contract. A `429` response means slow down; retry after a short sleep. Cursor pagination does not count against any result-window cap.

## Common Pitfalls
- Abstracts come as an inverted index (word→positions). Rebuild with: sort words by their smallest position, join with spaces. Do not ship the inverted index raw to the user — reconstruct it.
- `filter` values cannot contain unencoded commas (that would start a new filter) — URL-encode as `%2C`.
- `search` is relevance-ranked; `filter` is not. Combine them: `?search=foo&filter=publication_year:2024`.
- OpenAlex IDs come in two flavors: bare (`W2741809807`) and URL (`https://openalex.org/W2741809807`). Both are accepted; be consistent in downstream code.
- The `mailto` parameter is the *only* way to opt into the polite pool without a paid key — skip it at your own reliability risk.
- `cited_by_count` counts citations *in OpenAlex*, not Google Scholar. It is a lower bound.

## Example curl
```bash
# Open-access 2024 papers on graph neural networks, with polite-pool email
curl -s 'https://api.openalex.org/works?search=graph+neural+network&filter=publication_year:2024,is_oa:true&per_page=25&mailto=you@example.com'

# Single work by DOI
curl -s 'https://api.openalex.org/works/doi:10.1038/nature12373?mailto=you@example.com'

# Cursor pagination
curl -s 'https://api.openalex.org/works?filter=authorships.institutions.ror:https://ror.org/00f54p054&per_page=200&cursor=*&mailto=you@example.com'
```
