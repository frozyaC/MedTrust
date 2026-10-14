# Source relevance and multi-document context (v24)

## Classifier result

The deterministic classifier lives in `app/services/source_relevance.py`. It returns `score` (0–1), `label` (`relevant`, `partial`, `irrelevant`), `reason`, and `matched_terms`. It evaluates title, path, section, URL, and content. Weather queries additionally require weather evidence and a location match, with common transliteration variants for major Russian cities.

This is a transparent heuristic rather than a trained or LLM-based classifier. For web sources, the existing medical topic/intent checks remain in force; the common classifier result is also exposed in the API. HTTPS plus domain allowlisting is a separate gate and is not replaced by relevance scoring.

## Wiki chunk selection

`RagService.answer()` fetches a widened candidate pool to improve recall for composite questions. `_wiki_sufficient_docs()` annotates candidates, filters clear off-topic Wiki entries when relevant candidates exist, and ranks by relevance label/score, content-only fit, weighted RRF, and dense similarity. It chooses the best chunk from distinct articles first. Extra chunks from the same article are only used when their own body contains evidence for the current query.

For live weather questions, Wiki is never considered sufficient because stored documentation is not a current forecast. SearXNG is always attempted. If no relevant weather result survives filtering, MedTrust returns an explicit data-fetch failure instead of making up a current forecast.

## API diagnostics

- `sources[].relevance`: relevance assessment for a source actually eligible to be passed into the model.
- `retrieval[].source_relevance`: assessment combining title/path/section/URL and chunk text.
- `retrieval[].content_relevance`: assessment of chunk text alone; useful for finding chunks that match by article metadata but do not contain the requested fact.
- `retrieval[].eligible_for_answer`: indicates whether a Wiki chunk was selected into the prompt. It does not certify that the generated answer is factually correct.
- `sources[].used_in_answer`: indicates whether the corresponding `[Wn]` or `[WEBn]` label appeared in the answer. It is citation-presence telemetry, not validation of clinical accuracy.

## Manual test cases

1. `Погода Екатеринбург` — must query SearXNG even when Wiki has a high dense score; the accepted source must mention weather and match Ekaterinburg/Yekaterinburg.
2. `Как подготовиться к гастроскопии` — title/path/content variants of `подготовка` should match `подготовиться`; relevant low-dense Wiki passages must not be discarded by similarity alone.
3. `допуск на территорию и общая информация` — prompt should include the best useful chunks from both the parking/access article and the general-information article, and should not include a high-dense unrelated chunk.
4. `Какая температура тела у пациента при простуде?` — must not be mistaken for a live-weather request.


## Facet retrieval for compound queries (v24)

For a question that explicitly combines parking/access with a request to consult a named specialty, `RagService._split_multi_intent_question()` creates separate subqueries. Each subquery runs through hybrid search independently; duplicate chunk IDs are merged, and the candidate retains `_matched_query_aspects`. The response exposes these as `retrieval_queries` and `matched_query_aspects`. This specifically avoids a blended query embedding hiding the parking patient's general rules or the appointment assignment section.

The relevance classifier has domain-specific signals for two answer types:

- For branch-specific parking questions, the requested branch plus a `Для пациентов клиники` section and parking conditions are a strong match. A taxi-only section is downgraded unless the user asks about taxi/drop-off rules.
- For questions asking which doctor to book, the exact specialty in the Wiki metadata plus an appointment-assignment cue (for example, `Распределение записи` / `Консультативные приемы`) ranks the passage as directly answerable.

This is still a narrow, deterministic heuristic, not a universal intent decomposition model. The tests in `tests/test_multi_intent_retrieval.py` use the bundled Wiki export and fake retrieval/model clients. A full deployment test should use the indexed live Wiki and verify the actual `retrieval_queries`, source selections, and answer citations.
