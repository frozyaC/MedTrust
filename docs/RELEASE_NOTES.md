# MedTrust v23

## Changes

- Updated the GigaChat system prompt to prefer short bullet-structured answers (normally 3–7 bullets, fewer for simple requests) and numbered lists for procedures.
- Added a deterministic source-relevance classifier with `relevant`, `partial`, and `irrelevant` labels, numeric scores, reasons, and matched terms. It is used to classify Wiki passages and returned web sources.
- Added separate body-level relevance scoring for Wiki chunks so an unrelated section cannot borrow all of its relevance from the parent article title.
- Expanded the Wiki retrieval pool for `/api/v1/query` (minimum 12, capped at 30 candidates) and selected a diverse context across distinct documents before adding useful extra chunks. This addresses composite questions that need more than one Wiki article.
- Changed selection to consider topical relevance, body-level fit, weighted RRF, and dense similarity rather than sorting primarily by dense similarity. Clearly irrelevant Wiki candidates are excluded from the model prompt but remain available in `retrieval` for debugging.
- Added the source relevance assessments to the API: `sources[].relevance`, `retrieval[].source_relevance`, and `retrieval[].content_relevance`.
- Added a live-weather search path for queries such as `Погода Екатеринбург`. It always queries SearXNG, checks city matching (including common Russian/English spellings), and only accepts HTTPS results from the limited weather provider allowlist. If current forecast evidence is missing, it does not invent a temperature.
- Added regression tests for bullet prompt instructions, city-aware weather matching and answer generation, irrelevant-source exclusion, and combining different Wiki articles into one prompt.

## Limitations

The source-relevance classifier is deterministic lexical/metadata scoring, not a trained semantic classifier; it improves inspectability and ranking but can still miss paraphrases. Source relevance does not establish factual or clinical correctness. The benefit of bullet formatting for registrars' reading time has not been measured and needs a small A/B usability test.

## Tests

`pytest -q`: 81 passed in the local unit-test run using temporary stubs for unavailable PostgreSQL/pgvector and OpenAI client libraries. Live PostgreSQL, GigaChat, SearXNG, and provider HTTP responses were not exercised; run an integration test in the configured project environment before deployment.
