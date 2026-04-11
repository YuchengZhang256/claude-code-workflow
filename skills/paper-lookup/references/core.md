# CORE

## Overview
CORE (core.ac.uk) aggregates over 37 million open-access research outputs from repositories and journals worldwide — the largest collection of OA full texts. Best for: retrieving full text (not just metadata) for non-biomedical papers where PMC is not applicable, discovering OA copies in institutional repositories, and running searches that need full-text indexing. CORE is indispensable when you want body text for NLP/RAG over humanities, engineering, or social-science papers.

## Base URL
`https://api.core.ac.uk/v3/`

## Authentication
Required for almost all endpoints. Register a free account at `https://core.ac.uk/services/api` to get a key. Pass the key either as:
- HTTP header (preferred): `Authorization: Bearer <API_KEY>`
- Querystring: `?api_key=<API_KEY>`

Anonymous access is heavily limited and will not reliably return full text.

## Key Endpoints
- `GET /v3/search/works?q=<query>` — search the full-works index (metadata + full text). Returns scored hits.
- `GET /v3/search/outputs?q=<query>` — parallel endpoint for output-level search (legacy naming, same shape).
- `GET /v3/search/data-providers?q=<query>` — search institutional repositories and journals that CORE harvests from.
- `GET /v3/search/journals?q=<query>` — journal-level search.
- `GET /v3/works/<id>` — fetch a single work by CORE ID.
- `GET /v3/works/<id>/download` — download the full text (PDF or extracted text). May redirect to the hosted file.
- `GET /v3/data-providers/<id>` — details for an institutional provider.
- `GET /v3/journals/<id>` — details for a journal.

## Query Syntax
CORE uses an Elasticsearch-flavored query DSL in `q`:
- `AND`, `OR`, `NOT` (uppercase) for Boolean.
- `field:value` for field-scoped matches. Useful fields: `title`, `abstract`, `authors`, `yearPublished`, `fullText`, `doi`, `oai`, `language.code`.
- Phrase match with double quotes: `title:"machine learning"`.
- Range: `yearPublished>=2020`, `yearPublished:[2020 TO 2024]`.
- Existence: `_exists_:fullText` — only return records where CORE has full text indexed.
- Grouping with parentheses.

Examples:
- `q=title:"graph neural network" AND yearPublished>=2022&limit=20`
- `q=abstract:"causal discovery" AND _exists_:fullText`
- `q=authors:"Jane Smith" AND doi:10.1038/*`

Pagination: `offset=<n>` and `limit=<n>` (up to 100 per call). For deep crawls use the `scroll` parameter (`scroll=true` on first call; pass back the returned `scrollId`).

## Response Format
JSON. List endpoints return `{ totalHits, limit, offset, results: [ work, ... ], scrollId? }`. Each work has `id`, `doi`, `title`, `abstract`, `authors: [ { name } ]`, `yearPublished`, `publishedDate`, `publisher`, `language`, `documentType`, `fullText` (plain-text body when available; often truncated in search responses), `downloadUrl`, `sourceFulltextUrls: [...]`, `references: [...]`, `citations: [...]`, `dataProviders: [ { id, name, url } ]`, `oai`.

## Rate Limits
CORE uses a token-based quota per tier (from CORE's official docs):
- Unauthenticated: 100 tokens/day, 10 tokens/min burst.
- Registered personal: 1,000 tokens/day, 25 tokens/min.
- Academic (non-supporting institution): 5,000 tokens/day, 10 tokens/min.
- Supporting institutions: ~200k tokens/day on average with dedicated support.

Each search and download consumes tokens; large batch calls consume more. Monitor via response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Retry-After`.

## Common Pitfalls
- `fullText` in search hits may be truncated or omitted for size. To get the complete body, call `/works/<id>` or `/works/<id>/download`.
- The `download` endpoint may redirect (`302`) to an external host — follow redirects (`curl -L`).
- Not every work has full text — always check `_exists_:fullText` or verify `downloadUrl`/`sourceFulltextUrls` is non-empty before assuming you can retrieve the body.
- Daily quota is easy to exhaust — cache results locally, do not re-query the same term on every run.
- CORE harvests from repositories on a delay; new papers may take days/weeks to appear.
- Field names are singular for some filters (`yearPublished`, not `year`) — check the schema if a filter returns zero hits.

## Example curl
```bash
# Keyword search, require full text, 2024+ only
curl -s -H "Authorization: Bearer $CORE_API_KEY" \
  'https://api.core.ac.uk/v3/search/works?q=title:%22graph+neural+network%22+AND+yearPublished%3A%5B2024+TO+%2A%5D+AND+_exists_:fullText&limit=20'

# Fetch a single work
curl -s -H "Authorization: Bearer $CORE_API_KEY" \
  'https://api.core.ac.uk/v3/works/12345678'

# Download the full text (follow redirects)
curl -sL -H "Authorization: Bearer $CORE_API_KEY" \
  'https://api.core.ac.uk/v3/works/12345678/download' -o paper.pdf
```
