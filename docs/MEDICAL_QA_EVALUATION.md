# Medical QA quality requirements and evaluation

## Current answer path (v18)

The default request path uses one GigaChat generation call after retrieval. It does not call a second model to review or repair the answer. It runs bounded deterministic checks for source citations, supported numeric values and units, adult/adolescent scope, selected migraine-aura contradictions, unsupported clinical concepts, and source-backed diagnostic coverage. When checks fail, the service returns a source excerpt or a short insufficiency response instead of spending additional completion tokens on repeated repair attempts.

`answer_reviewed=true` means the answer passed these implemented deterministic checks. It is not proof of clinical correctness and is not a substitute for clinician review. The validator is pattern-based, intentionally limited, and can still produce false positives or miss errors not covered by its rules.

## Per-request resource limits

Default configuration in `.env.example`:

- `GIGACHAT_MAX_TOKENS=450`: caps generated completion length.
- `RAG_MAX_WEB_SOURCES=2`: at most two web results are passed to the generator.
- `RAG_MAX_WIKI_SOURCES=3`: at most three eligible Wiki.js chunks are passed to the generator.
- `RAG_MAX_SOURCE_CHARS=4200`: caps the text sent for each source.
- `RAG_MAX_HISTORY_MESSAGES=4` and `RAG_MAX_HISTORY_MESSAGE_CHARS=600`: only a bounded tail of the recent dialogue enters the prompt.
- `MEMORY_SUMMARY_ENABLED=false`: avoids extra GigaChat calls for periodic history summarization. Enabling it may incur additional completion calls when the summary threshold is reached.

A typical successful query uses one query-embedding API call and one GigaChat completion call. Requests rejected by the scope guard or requests without usable evidence can avoid the completion call. Usage reporting is returned in `resource_usage`: provider-reported GigaChat input/output/total tokens where available, otherwise an input-token estimate; embedding usage is exposed separately when the embeddings provider returns usage metadata. Estimate values are not billing records.

## Why 0.95 cannot be claimed yet

Token limits and deterministic checks can reduce cost and catch known error patterns, but they do not establish precision, recall, or accuracy above 0.95. Those values require a labelled benchmark and independent clinical review of atomic claims. Unit tests measure specific software invariants, not clinical correctness across all questions.

## Recommended metric definitions

- **Evidence precision:** relevant and usable retrieved sources divided by all retrieved sources.
- **Evidence recall:** relevant gold-standard sources retrieved divided by all relevant sources in the labelled reference set.
- **Claim precision:** medically substantive answer claims directly supported by the cited source text divided by all medically substantive claims in the answer.
- **Fact recall:** gold-standard facts required to answer the question and present in the answer divided by all required gold-standard facts for that question.
- **Answer accuracy:** answers adjudicated correct for the question and patient context divided by all evaluated answers. Track critical-error rate separately; a high average must not mask unsafe errors.

## Evaluation protocol

1. Create a versioned, representative set of real queries, including diagnosis, symptoms, tests, treatment, dosage, triage/routing, follow-ups, insufficient-evidence cases, misleading keyword matches, and conflicting/outdated sources.
2. For each case, record the intended population, required facts, prohibited claims, relevant/irrelevant source URLs, acceptable uncertainty behaviour, and whether referral/red-flag information is required.
3. Have two qualified reviewers independently annotate expected facts and answer claims; adjudicate disagreements. Do not use the model that generates answers as the sole judge of its own correctness.
4. Report evidence precision/recall separately from answer claim precision/recall/accuracy. Break results down by question type and report confidence intervals and critical errors.
5. Accept a release against the `>0.95` target only after the frozen held-out set demonstrates that each defined metric exceeds 0.95 under the agreed scoring rules. Until then, report measured results and their limitations instead of claiming the target is met.

## Limitations

The deterministic validation is not a general-purpose medical natural-language-inference system. It may miss unsupported claims that do not match its patterns or flag valid claims when evidence text is incomplete. The system should be treated as an assistant for source-grounded knowledge access, not an autonomous diagnostic system. Before high-stakes deployment, combine a labelled benchmark, red-team cases, clinical review, and operational monitoring.


## Short NICE diagnostic FAQ path (v19)

For the bounded question about migraine diagnosis in adults, if the fetched NICE CG150 recommendation text contains the required diagnostic sections, RAG returns a concise evidence-grounded template without a GigaChat completion call. The template includes pain features and duration, aura, frequency/diary guidance, and warning signs, with `[WEB1]` citation blocks. If only the NICE comparison-table excerpt is available, a shorter partial answer reports only the pain-location/quality features present in that excerpt and explicitly states that the full diagnostic criteria cannot be confirmed from the excerpt. It omits absent duration/aura/red-flag details rather than guessing.

The section extractor accepts both `develop over at least 5 minutes` and `develop gradually over at least 5 minutes`, preserving aura criteria when the site text varies slightly. Tests verify that the compact excerpt retains duration, aura, diary, and red-flag evidence. This behavior reduces cost for this FAQ but is not a validated medical benchmark and does not establish precision/recall/accuracy above 0.95.
