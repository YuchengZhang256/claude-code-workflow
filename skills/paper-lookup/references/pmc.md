# PMC (PubMed Central)

## Overview
PMC is NCBI's free archive of full-text biomedical and life-sciences articles — over 10 million articles in JATS XML. Best for: retrieving the full text (not just abstracts) of open-access biomedical papers, converting between PMID/PMCID/DOI, and pulling tables/figures/references from JATS. PMC reuses the same E-utilities infrastructure as PubMed plus a dedicated ID Converter and the OA Web Service for PDFs and bulk packages.

## Base URL
- E-utilities: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- ID Converter: `https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/`
- OA Web Service (PDF/tarball links): `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi`

## Authentication
Same as PubMed: optional `api_key`. Rate limit is 3 req/sec without key, 10 req/sec with key. The ID Converter and OA service do not require auth. Include `&tool=<name>&email=<addr>` as a courtesy.

## Key Endpoints
- `esearch.fcgi?db=pmc&term=<query>` — search PMC by keyword; returns PMCIDs (numeric internally; the `PMC` prefix is display-only).
- `efetch.fcgi?db=pmc&id=<pmcid>&rettype=full&retmode=xml` — full JATS XML for an article (abstract, body, tables, references).
- `elink.fcgi?dbfrom=pubmed&db=pmc&id=<pmid>` — find PMC records linked to a PubMed PMID.
- ID Converter: `idconv/v1.0/?ids=<comma_list>&idtype=pmid|pmcid|doi&format=json` — translate between PMID, PMCID, DOI, and Manuscript IDs.
- OA service: `oa.fcgi?id=PMC7029759` — returns XML with `<link>` elements pointing to tarballs (JATS XML + media) and, when available, a direct PDF URL.

## Query Syntax
Same field-tag grammar as PubMed (`[tiab]`, `[ti]`, `[au]`, `[dp]`, `[mh]`). Additional useful filters:
- `"open access"[filter]` — restrict to OA subset.
- `"pubmed pmc"[sb]` — subset filter for PMC-indexed records.
- Examples:
  - `single cell[tiab] AND "open access"[filter] AND 2024[dp]`
  - `cancer[mh] AND hasabstract[text]`

## Response Format
- `efetch` returns JATS XML — articles wrapped in `<article>` with `<front>` (metadata), `<body>` (sections/paragraphs), `<back>` (references). No JSON option.
- ID Converter JSON: `{ records: [ { pmcid, pmid, doi, versions, ... } ], status }`.
- OA service returns XML with `<record>` elements and `<link format="pdf" href="ftp://...">` or `format="tgz"`.

## Rate Limits
- E-utilities: 3/sec without key, 10/sec with key — shared with PubMed traffic.
- ID Converter: no documented hard limit, but throttle to a few requests/sec.
- OA service: same — be polite, batch IDs in a single call where possible.

## Common Pitfalls
- PMC full text is JATS XML, not HTML and not JSON. Use an XML parser (lxml, BeautifulSoup with `xml` parser, xmllint).
- Not every PubMed article has a PMC copy. Use ID Converter first to verify a PMCID exists.
- The `PMC` prefix is stripped internally by efetch — both `PMC7029759` and `7029759` usually work, but the ID Converter wants the exact form you tell it via `idtype`.
- Some articles are in PMC but NOT open access (e.g., author manuscripts under embargo). Check `oa.fcgi` before assuming you can redistribute.
- Figures and supplementary media are only in the tarball, not in the inline XML.

## Example curl
```bash
# Convert a DOI to PMCID/PMID
curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=10.1038/s41586-020-2012-7&idtype=doi&format=json"

# Fetch full JATS XML
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=7029759&rettype=full&retmode=xml&api_key=$NCBI_API_KEY"

# Get OA package link
curl -s "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC7029759"
```
