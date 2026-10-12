# Medical QA quality requirements and evaluation

## Current answer path (v22)

There is no input scope guard based on a fixed list of medical keywords. Query text is sent through hybrid Wiki retrieval, so everyday formulations such as “Как подготовиться к гастроскопии?” are not rejected before search. Dense, lexical and path scores rank the candidates. A score threshold can trigger SearXNG fallback, but it no longer prevents the best available Wiki passages from being sent to the model.

Web results still pass HTTPS-domain allowlisting and topic/body relevance checks before entering the prompt. These checks protect source selection; they do not block answer generation. The request path does not run a post-generation checklist, and an answer is not replaced just because a citation is missing or malformed. Source labels are observed non-blockingly. `answer_validation_mode=non_blocking_diagnostics_only`; `sources` includes retrieved candidates and their `used_in_answer` flag.

If no usable source evidence is available, GigaChat still receives the question and can answer from general knowledge. It is instructed to disclose that MedTrust did not return confirming materials and not to invent Wiki content or citations. Such a response may be useful, but it is not source-grounded and should be assessed separately. For clinical use, medical correctness and critical-error rate must be evaluated with a labelled benchmark and independent clinical review.

## Per-request resource limits

Default configuration in `.env.example`:

- `GIGACHAT_MAX_TOKENS=450`: caps generated completion length.
- `RAG_MAX_WEB_SOURCES=2`: at most two web results are passed to the generator.
- `RAG_MAX_WIKI_SOURCES=3`: at most three Wiki chunks are passed to the generator, selected by score rather than filtered by a hard threshold.
- `RAG_MAX_SOURCE_CHARS=4200`: caps the text sent for each source.
- `RAG_MAX_HISTORY_MESSAGES=4` and `RAG_MAX_HISTORY_MESSAGE_CHARS=600`: only a bounded tail of the recent dialogue enters the prompt.
- `MEMORY_SUMMARY_ENABLED=false`: avoids extra GigaChat calls for periodic history summarization. Enabling it may incur additional completion calls when the summary threshold is reached.

A request that needs a generated answer uses one GigaChat completion call, even when sources are absent. Certain source-grounded templates can avoid GigaChat. Usage reporting is returned in `resource_usage`; estimated input tokens are not billing records.

## Why 0.95 cannot be claimed yet

Token limits and source selection do not establish precision, recall, or accuracy above 0.95. Those values require a labelled benchmark and independent clinical review of atomic claims. Unit tests measure software behavior, not clinical correctness across all questions.

## Recommended metric definitions

- **Evidence precision:** relevant and usable retrieved sources divided by all retrieved sources.
- **Evidence recall:** relevant gold-standard sources retrieved divided by all relevant sources in the labelled reference set.
- **Claim precision:** medically substantive answer claims directly supported by cited source text divided by all medically substantive claims in the answer.
- **Fact recall:** gold-standard facts required to answer the question and present in the answer divided by all required gold-standard facts for that question.
- **Answer accuracy:** answers adjudicated correct for the question and patient context divided by all evaluated answers. Track critical-error rate separately; a high average must not mask unsafe errors.
