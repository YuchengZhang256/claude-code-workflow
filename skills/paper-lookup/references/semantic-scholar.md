# Semantic Scholar

## Overview
Semantic Scholar (S2) is Allen Institute for AI's academic search engine, backed by a graph of over 200 million papers with citation/reference links, author disambiguation, AI-generated TLDRs, embeddings (SPECTER/SPECTER2), and paper recommendations. Best for: citation graph traversal (who cites whom), author profile lookups, paper-to-paper recommendations, relevance-scored search across CS/biomedical/multidisciplinary content, and batch fetches for embeddings or features. Two sibling APIs: Academic Graph API and Recommendations API.

## Base URL
- Academic Graph: `https://api.semanticscholar.org/graph/v1/`
- Recommendations: `https://api.semanticscholar.org/recommendations/v1/`
- Datasets: `https://api.semanticscholar.org/datasets/v1/` (bulk snapshots)

## Authentication
API key is optional but strongly recommended — without one, requests go to a heavily throttled shared pool and you will see `429`s fast. Request a free key at `https://www.semanticscholar.org/product/api#api-key-form`. Pass it in the `x-api-key` header.

## Key Endpoints
- `GET /graph/v1/paper/search?query=<text>` — relevance-scored keyword search (fast path).
- `GET /graph/v1/paper/search/bulk?query=<text>` — bulk-search variant for large result sets with a `token` cursor.
- `GET /graph/v1/paper/<paper_id>` — details for one paper. `<paper_id>` accepts S2 IDs (40-char hex), `DOI:10.1038/...`, `ARXIV:2103.15348`, `PMID:34567890`, `PMCID:PMC1234567`, `CorpusId:<n>`, `URL:<arxiv_or_acl_url>`.
- `GET /graph/v1/paper/<paper_id>/citations` — papers that cite this one.
- `GET /graph/v1/paper/<paper_id>/references` — papers cited by this one.
- `POST /graph/v1/paper/batch` — fetch up to 500 papers in one call (body: `{"ids": ["DOI:...", ...]}`).
- `GET /graph/v1/author/search?query=<name>` — author disambiguation search.
- `GET /graph/v1/author/<author_id>` and `/papers` — author profile and their publications.
- `GET /recommendations/v1/papers/forpaper/<paper_id>` — "more like this" for a single seed.
- `POST /recommendations/v1/papers` — recommendations from a list of positive/negative seed papers.

## Query Syntax
The `query` parameter is free-text (no field tags, no Boolean). Narrow results with additional parameters:
- `fields=title,authors,year,abstract,citationCount,externalIds,tldr,openAccessPdf` — select returned fields (required for most interesting data; defaults are minimal).
- `year=2024` or `year=2020-2024` or `year=2020-` — publication year filter.
- `publicationTypes=JournalArticle,Conference,Review` — comma list.
- `venue=Nature,ICML,NeurIPS` — venue filter.
- `openAccessPdf` — require an OA PDF.
- `fieldsOfStudy=Computer Science,Biology` — subject area filter.
- `offset` + `limit` (relevance search, max limit 100, max offset 1000) OR `token` for bulk search (no offset cap).

## Response Format
JSON. Search: `{ total, offset, next, data: [ paper, ... ] }`. Bulk search: `{ total, token, data: [...] }` — pass the returned `token` as `&token=<val>` on the next call. Paper object fields depend on the `fields` parameter: `paperId`, `externalIds { DOI, PubMed, ArXiv, CorpusId, ... }`, `title`, `abstract`, `venue`, `year`, `authors: [{ authorId, name }]`, `citationCount`, `referenceCount`, `influentialCitationCount`, `tldr: { model, text }`, `openAccessPdf: { url, status }`, `embedding` (SPECTER), `s2FieldsOfStudy`.

## Rate Limits
- Without API key: ~1 req/sec per IP (shared pool), easy to hit 429.
- With API key: default 1 req/sec dedicated, escalatable to 10+ on request to Semantic Scholar.
- `/paper/batch` is the right tool for high-volume ID resolution — one call fetches up to 500 papers.
- Respect `Retry-After` on 429s.

## Common Pitfalls
- Default `fields` response is nearly empty — always pass `fields=...` with what you actually need.
- Identifier prefixes are mandatory for non-S2 IDs: `DOI:`, `ARXIV:`, `PMID:`, `PMCID:`, `CorpusId:`. A bare DOI will not resolve.
- `paper/search` caps at 100 results per page and 1000 offset — for anything bigger, switch to `paper/search/bulk` with the `token`.
- `citationCount` is citations Semantic Scholar *knows about* — usually close to but not identical to OpenAlex or Google Scholar counts.
- `tldr` is only populated for papers where the model ran successfully. Treat absence as normal.
- Batch endpoint uses `POST` with a JSON body, not `GET` — and the `fields` parameter goes in the querystring, not the body.
- Shared-pool 429s cascade: once you start getting throttled, sequential calls will keep failing. Sleep 10–30 seconds before retrying.

## Example curl
```bash
# Keyword search with rich fields
curl -s -H "x-api-key: $S2_API_KEY" \
  'https://api.semanticscholar.org/graph/v1/paper/search?query=causal+inference+observational&limit=20&fields=title,year,authors,citationCount,tldr,externalIds'

# Paper details by DOI
curl -s -H "x-api-key: $S2_API_KEY" \
  'https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373?fields=title,abstract,citationCount,references.title,references.year'

# Batch lookup
curl -s -X POST -H "x-api-key: $S2_API_KEY" -H "Content-Type: application/json" \
  -d '{"ids":["DOI:10.1038/nature12373","ARXIV:2103.15348"]}' \
  'https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,year,citationCount'

# Recommendations from a seed
curl -s -H "x-api-key: $S2_API_KEY" \
  'https://api.semanticscholar.org/recommendations/v1/papers/forpaper/DOI:10.1038/nature12373?fields=title,year&limit=10'
```
