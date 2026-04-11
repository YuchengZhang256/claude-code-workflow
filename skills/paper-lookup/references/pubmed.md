# PubMed (NCBI E-utilities)

## Overview
PubMed indexes over 37 million citations for biomedical literature from MEDLINE, life science journals, and online books. Access is provided through NCBI's E-utilities (Entrez Programming Utilities), a stable REST-style interface. Best for: biomedical and clinical literature search, MeSH-indexed queries, linking between NCBI databases (PubMed, PMC, Gene, Protein, etc.), and retrieving abstracts by PMID.

## Base URL
`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

## Authentication
API key is optional but strongly recommended. Without a key the rate limit is 3 requests/second per IP; with a key it rises to 10 requests/second. Obtain a key at `https://www.ncbi.nlm.nih.gov/account/settings/` (free; requires an NCBI account). Pass the key as `&api_key=YOUR_KEY`. Also include `&tool=<name>&email=<addr>` so NCBI can contact you if your usage misbehaves.

## Key Endpoints
- `esearch.fcgi?db=pubmed&term=<query>` — search PubMed; returns a list of PMIDs plus a WebEnv/QueryKey for history-server follow-ups.
- `esummary.fcgi?db=pubmed&id=<pmid_list>` — retrieve document summaries (title, authors, journal, pub date, DOI).
- `efetch.fcgi?db=pubmed&id=<pmid_list>&rettype=abstract&retmode=xml` — retrieve full records including abstracts.
- `elink.fcgi?dbfrom=pubmed&db=pmc&id=<pmid>` — follow links, e.g. from PubMed to PMC full text.
- `einfo.fcgi?db=pubmed` — field descriptions and database statistics.
- `epost.fcgi?db=pubmed&id=<pmid_list>` — upload a set of IDs to the history server for batch work.

## Query Syntax
PubMed queries use Entrez field tags in square brackets. Common tags:
- `[tiab]` — title/abstract
- `[ti]` — title only
- `[au]` — author
- `[mh]` — MeSH term
- `[dp]` — date of publication (`"2020"[dp]` or `"2020/01/01"[dp] : "2020/12/31"[dp]`)
- `[la]` — language
- `[pt]` — publication type (e.g., `"review"[pt]`)

Boolean operators `AND`, `OR`, `NOT` are uppercase. Phrase match with double quotes. Examples:
- `CRISPR[tiab] AND gene therapy[tiab] AND 2023[dp]`
- `(Smith J[au]) AND (cancer[mh])`
- `"machine learning"[tiab] AND "clinical decision"[tiab]`

## Response Format
`esearch` returns XML by default; add `&retmode=json` for JSON. JSON top-level: `esearchresult.count`, `esearchresult.idlist`, `esearchresult.webenv`, `esearchresult.querykey`. `esummary` JSON returns `result.<pmid>` objects with `title`, `authors`, `source`, `pubdate`, `elocationid`, `articleids`. `efetch` returns JATS-like PubMedArticle XML only (no JSON) — parse with an XML tool.

## Rate Limits
- Without API key: 3 requests/sec per IP.
- With API key: 10 requests/sec.
- Large downloads (>10k records) should be done during off-peak hours (9 PM–5 AM US Eastern on weekdays or any time on weekends) per NCBI policy.
- Use `&usehistory=y` on esearch and batch-fetch via WebEnv/QueryKey instead of sending thousands of IDs per URL.

## Common Pitfalls
- `efetch` does not return JSON for PubMed — only XML. Plan a parser.
- `retmax` defaults to 20; set it explicitly (max 10,000 per call; use history server beyond that).
- Boolean operators must be UPPERCASE (`AND`, not `and`).
- Field tags are case-insensitive but always inside `[]`, e.g. `[tiab]`, not `(tiab)`.
- Do not hammer the endpoint in parallel — the per-IP cap applies across concurrent requests.

## Example curl
```bash
# Search, then fetch abstracts for first 5 hits
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=CRISPR+AND+2024[dp]&retmode=json&retmax=5&api_key=$NCBI_API_KEY"

curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=39123456,39123457&rettype=abstract&retmode=xml&api_key=$NCBI_API_KEY"
```
