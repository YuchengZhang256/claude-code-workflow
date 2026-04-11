# arXiv

## Overview
arXiv is the primary preprint server for physics, mathematics, computer science, quantitative biology, quantitative finance, statistics, electrical engineering, systems science, and economics — over 2.4 million preprints. The arXiv API supports keyword search with field prefixes, multi-field Boolean queries, date-sorted browsing, and ID-list lookups. It is one of the few databases in this skill that returns Atom 1.0 XML instead of JSON — expect an XML parser on the downstream side.

## Base URL
`http://export.arxiv.org/api/query`

## Authentication
None. No API key, no registration. The only "auth" signal is your courtesy rate-limiting.

## Key Endpoints
There is a single endpoint, `GET /api/query`, parameterized by querystring:
- `search_query=<expression>` — the keyword query (see syntax below).
- `id_list=<comma_list>` — retrieve specific arXiv IDs (can combine with `search_query` to filter).
- `start=<n>` — 0-based pagination offset.
- `max_results=<n>` — results per request; hard cap is 2000 per call, 30000 total for a query.
- `sortBy=relevance|lastUpdatedDate|submittedDate` — sort field.
- `sortOrder=ascending|descending` — sort direction.

## Query Syntax
Field prefixes in `search_query`:
- `ti:` — title
- `au:` — author
- `abs:` — abstract
- `co:` — comments
- `jr:` — journal reference
- `cat:` — subject category (e.g., `cs.LG`, `stat.ML`, `math.PR`)
- `rn:` — report number
- `all:` — all of the above

Boolean operators: `AND`, `OR`, `ANDNOT` (uppercase). Group with URL-encoded parentheses (`%28`, `%29`). Phrases need URL-encoded double quotes (`%22`). Examples:
- `search_query=ti:%22graph+neural+network%22+AND+cat:cs.LG`
- `search_query=au:hinton+AND+abs:attention&sortBy=submittedDate&sortOrder=descending`
- `id_list=2103.15348,2305.18290` — direct lookup.

## Response Format
Atom 1.0 XML. Top-level `<feed>` contains metadata about the query and a list of `<entry>` elements. Each `<entry>` has:
- `<id>` — canonical abs URL (e.g., `http://arxiv.org/abs/2103.15348v2`)
- `<title>`, `<summary>` — abstract text
- `<author><name>` — one per coauthor
- `<published>`, `<updated>` — ISO 8601 timestamps
- `<arxiv:primary_category term="cs.LG"/>` — primary subject (needs the `xmlns:arxiv="http://arxiv.org/schemas/atom"` namespace)
- `<link rel="alternate" ...>` (HTML abs page) and `<link title="pdf" ...>` (PDF URL)
- `<arxiv:doi>` — when the paper has been assigned a DOI
- `<arxiv:journal_ref>` — when published

`<opensearch:totalResults>` inside the feed tells you how many total hits exist — useful for paginating with `start`.

## Rate Limits
arXiv asks clients to insert a 3-second delay between calls. There is no enforced HTTP limit, but the service is shared infrastructure — hammering it risks an IP ban. Batch where possible: a single `max_results=200` call is far kinder than 200 single-result calls. For scraping-scale work, use the OAI-PMH interface instead.

## Common Pitfalls
- Response is Atom XML, not JSON. Do NOT try to `jq` it; use `xmltodict`, `lxml`, or `feedparser` (Python), or `xmllint --xpath`.
- `search_query` phrases must be URL-encoded (`%22...%22`), not raw `"..."`.
- The `+` in querystrings is interpreted as a space by some HTTP clients — if in doubt, use `%20` for space and a literal `+` only as the `AND` joiner between terms.
- `sortBy=relevance` can return stale or irrelevant top hits for generic queries — for recency use `sortBy=submittedDate&sortOrder=descending`.
- The arXiv ID namespacing changed in April 2007 (old: `math.PR/0601001`, new: `0704.0001`). Modern IDs are `YYMM.NNNNN` (5 digits since 2015).
- Versioned IDs (`2103.15348v3`) and unversioned (`2103.15348`) both work, but versioned returns that specific version's metadata.
- Respect the 3-second delay — especially in parallel-fanout code, serialize arXiv calls.

## Example curl
```bash
# Keyword search with category filter, most recent first
curl -s 'http://export.arxiv.org/api/query?search_query=ti:%22diffusion+model%22+AND+cat:cs.LG&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending'

# Direct ID lookup
curl -s 'http://export.arxiv.org/api/query?id_list=2103.15348,2305.18290'
```
