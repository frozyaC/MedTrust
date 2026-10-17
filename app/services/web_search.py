from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlparse

import requests

from app.core.config import get_settings
from app.services.safety import (
    DEFAULT_SAFE_DOMAINS,
    LOCAL_DISCOVERY_SAFE_DOMAINS,
    WEATHER_SAFE_DOMAINS,
    is_safe_domain,
)
from app.services.source_relevance import (
    classify_source_relevance, is_weather_query, preparation_evidence_problem,
)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    rank: int
    domain: str
    # "verified" means the search adapter's topic/evidence checks passed.
    # RAG may retain a weak but plausibly related result as "unverified" rather
    # than discarding its link, but it must never count it as confirmed evidence.
    verification_status: str = "verified"
    verification_note: str | None = None


@dataclass(frozen=True)
class WebSearchResponse:
    status: str
    results: list[WebSearchResult]
    error: str | None = None
    attempted_queries: list[str] | None = None


# A source must match a meaningful topic from the query. These bilingual families
# cover common conditions that often have different names in Russian and English.
# Unknown topics are checked with conservative token overlap below.
_TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "ct_scan": (
        r"(?<![a-zа-яё])ct(?:\s+scan)?(?![a-zа-яё])",
        r"computed\s+tomograph\w*",
        r"computerized\s+tomograph\w*",
        r"компьютерн\w*\s+томограф\w*",
        r"(?<![а-яё])кт(?![а-яё])",
    ),
    "gastroscopy": (
        r"gastroscop\w*", r"upper\s+endoscop\w*", r"esophagogastroduodenoscop\w*",
        r"гастроскоп\w*", r"фгдс", r"эзофагогастродуоденоскоп\w*",
    ),
    "biochemistry": (
        r"biochemical\s+(?:blood\s+)?test", r"blood\s+chemistry", r"serum\s+chemistry",
        r"биохим\w*\s+(?:анализ\w*\s+)?кров\w*", r"биохим\w*\s+анализ\w*",
    ),
    "preoperative_tests": (
        r"preoperative\s+(?:blood\s+)?tests?", r"pre-?operative\s+testing", r"pre-?op\s+tests?",
        r"предоперацион\w*\s+(?:анализ\w*|обследован\w*|исследован\w*)",
    ),
    "urology_tests": (
        r"urolog\w*\s+tests?", r"urinalysis", r"urine\s+test(?:s)?", r"urological\s+investigation\w*",
        r"уролог\w*\s+(?:анализ\w*|обследован\w*|исследован\w*)",
    ),
    "blood_test": (
        r"blood\s+tests?", r"complete\s+blood\s+count", r"\bcbc\b",
        r"анализ\w*\s+кров\w*", r"сдач\w*\s+кров\w*", r"\bоак\b",
    ),
    "migraine": (r"мигрен\w*", r"migrain\w*"),
    "me_cfs": (
        r"myalgic\s+encephalomyelitis",
        r"chronic\s+fatigue\s+syndrome",
        r"миалгическ\w*\s+энцефаломиелит\w*",
        r"синдром\s+хроническ\w*\s+усталост\w*",
    ),
    "multiple_sclerosis": (
        r"multiple\s+sclerosis",
        r"рассеянн\w*\s+склероз\w*",
    ),
    "hypertension": (
        r"hypertension",
        r"high\s+blood\s+pressure",
        r"гипертенз\w*",
        r"гипертони\w*",
    ),
    "diabetes": (r"diabet\w*", r"диабет\w*"),
    "asthma": (r"asthma\w*", r"астм\w*"),
    "stroke": (r"stroke\w*", r"инсульт\w*"),
    "epilepsy": (r"epilep\w*", r"эпилепс\w*"),
    "depression": (r"depress\w*", r"депресс\w*"),
    "pneumonia": (r"pneumoni\w*", r"пневмони\w*"),
    "osteoarthritis": (r"osteoarthritis", r"остеоартроз\w*"),
    "arthritis": (r"(?<!osteo)arthritis\w*", r"артрит\w*"),
    "heart_failure": (
        r"heart\s+failure",
        r"сердечн\w*\s+недостаточност\w*",
    ),
    "atrial_fibrillation": (
        r"atrial\s+fibrillation",
        r"фибрилляц\w*\s+предсерд\w*",
    ),
    "myocardial_infarction": (
        r"myocardial\s+infarction",
        r"heart\s+attack",
        r"инфаркт\w*\s+ми[оа]кард\w*",
    ),
    "parkinsons_disease": (
        r"parkinson\w*(?:\s+disease)?",
        r"болезн\w*\s+паркинсон\w*",
    ),
    "alzheimers_disease": (
        r"alzheimer\w*(?:\s+disease)?",
        r"болезн\w*\s+альцгеймер\w*",
    ),
    "copd": (
        r"copd",
        r"chronic\s+obstructive\s+pulmonary\s+disease",
        r"хроническ\w*\s+обструктивн\w*\s+болезн\w*\s+лёгк\w*",
        r"хроническ\w*\s+обструктивн\w*\s+болезн\w*\s+легк\w*",
    ),
    "covid": (r"covid(?:[-\s]?19)?", r"коронавирус\w*", r"ковид\w*"),
    "influenza": (r"influenza\w*", r"грипп\w*"),
    "anemia": (r"anaemia\w*", r"anemia\w*", r"анеми\w*"),
    "kidney_disease": (
        r"chronic\s+kidney\s+disease",
        r"kidney\s+disease",
        r"болезн\w*\s+почек",
        r"почечн\w*\s+недостаточност\w*",
    ),
    "reflux": (
        r"gastro.?oesophageal\s+reflux",
        r"gastro.?esophageal\s+reflux",
        r"гастроэзофагеальн\w*\s+рефлюкс\w*",
    ),
    "appendicitis": (r"appendicit\w*", r"аппендицит\w*"),
    "endometriosis": (r"endometriosis", r"эндометриоз\w*"),
    "rheumatoid_arthritis": (
        r"rheumatoid\s+arthritis",
        r"ревматоидн\w*\s+артрит\w*",
    ),
    "back_pain": (
        r"low\s+back\s+pain",
        r"back\s+pain",
        r"боль\w*\s+в\s+спин\w*",
        r"боль\w*\s+в\s+поясниц\w*",
    ),
    "anxiety_disorder": (
        r"anxiety\s+disorder",
        r"generalized\s+anxiety",
        r"тревожн\w*\s+расстройств\w*",
    ),
}
_COMPILED_TOPIC_PATTERNS = {
    topic: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for topic, patterns in _TOPIC_PATTERNS.items()
}

_INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "preparation": (
        r"prepar\w*", r"fasting", r"before\s+(?:the\s+)?(?:test|scan|procedure)",
        r"подготов\w*", r"натощак", r"перед\s+(?:сдач\w*|анализ\w*|исследован\w*|процедур\w*)",
        r"что\s+(?:можно|нельзя|нужно)\s+(?:есть|пить|делать)\s+перед",
        r"можно\s+ли.{0,100}(?:есть|пить|курить|поесть|покурить).{0,80}перед",
        r"(?:поесть|покурить|курить).{0,80}перед",
        r"eat\w*|drink\w*|avoid\s+smoking|smoking\s+before|before.{0,25}(?:scan|exam|imaging|test)",
    ),
    "comparison": (
        r"compar\w*", r"differ\w*", r"difference\w*", r"чем\s+отлич\w*", r"разниц\w*", r"сравнен\w*",
    ),
    "diagnosis": (r"diagnos\w*", r"диагност\w*", r"диагноз\w*"),
    "treatment": (
        r"treat\w*", r"therap\w*", r"management", r"лечени\w*", r"терап\w*",
        r"лечебн\w*",
    ),
    "recommendations": (
        r"recommend\w*", r"guideline\w*", r"guidance", r"рекомендац\w*",
        r"клиническ\w*\s+рекомендац\w*",
    ),
    "prevention": (r"prevent\w*", r"prevention", r"профилактик\w*"),
    "symptoms": (r"symptom\w*", r"signs?", r"симптом\w*", r"признак\w*"),
    "tests": (
        r"test\w*", r"screen\w*", r"investigation\w*", r"анализ\w*",
        r"обследован\w*", r"исследован\w*",
    ),
    "dosage": (
        r"dosage", r"dose\w*", r"дозиров\w*", r"доз\w*", r"приём\w*",
        r"прием\w*",
    ),
}
_COMPILED_INTENT_PATTERNS = {
    intent: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for intent, patterns in _INTENT_PATTERNS.items()
}
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_STOP_WORDS = {
    "а", "без", "бы", "быть", "в", "во", "вот", "все", "всех", "вы", "где",
    "для", "до", "его", "ее", "её", "если", "же", "за", "и", "из", "или",
    "им", "их", "как", "какая", "какие", "какой", "каком", "когда", "кто",
    "ли", "мне", "мы", "на", "над", "не", "него", "нее", "неё", "ни", "но",
    "о", "об", "однако", "он", "она", "они", "оно", "от", "по", "под", "при",
    "про", "с", "со", "так", "также", "то", "того", "тоже", "у", "уже", "что",
    "чтобы", "это", "этот", "эта", "эти", "этом", "я", "the", "a", "an", "and",
    "are", "as", "at", "be", "by", "can", "could", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "should", "that", "the",
    "this", "to", "was", "were", "what", "when", "where", "which", "who", "why",
    "with", "would", "you", "your",
}
_GENERIC_PREFIXES = (
    # Russian query intent and general medical vocabulary.
    "современ", "новейш", "актуальн", "рекомендац", "диагност", "взросл", "пациент",
    "врач", "медицин", "болезн", "заболев", "симптом", "лечени", "лечеб", "лечит",
    "терап", "профилактик", "причин", "клиническ", "оценк", "обследован", "осмотр",
    "исследован", "информац", "помощ", "подход", "руководств", "данн", "методик",
    "признак", "состояни", "проявлен", "эффективн", "безопасн", "обзор", "вопрос",
    # English query intent and general medical vocabulary.
    "modern", "current", "latest", "recommend", "guideline", "diagnos", "adult",
    "patient", "medical", "disease", "symptom", "treat", "therap", "prevent", "cause",
    "clinical", "assess", "examin", "research", "information", "care", "approach",
    "evidence", "method", "sign", "condition", "effective", "safety", "overview",
    "review", "question", "management",
)
_RUSSIAN_SUFFIXES = tuple(sorted((
    "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими", "иях", "ах",
    "ях", "ией", "иям", "ыми", "ими", "ью", "ия", "ие", "ые", "ое", "ая", "яя",
    "ой", "ий", "ый", "ую", "юю", "ов", "ев", "ей", "ам", "ям", "ом", "ем",
    "а", "я", "ы", "и", "у", "ю", "е", "о", "ь",
), key=len, reverse=True))
_ENGLISH_SUFFIXES = ("ization", "ations", "ation", "ments", "ment", "ingly", "edly", "ing", "ed", "es", "s")


_TOPIC_ENGLISH_TERMS: dict[str, str] = {
    "ct_scan": "CT scan computed tomography",
    "gastroscopy": "gastroscopy upper endoscopy",
    "biochemistry": "biochemical blood test blood chemistry",
    "preoperative_tests": "preoperative tests preoperative assessment",
    "urology_tests": "urology tests urinalysis urine test",
    "blood_test": "blood test",
    "migraine": "migraine",
    "me_cfs": "myalgic encephalomyelitis chronic fatigue syndrome",
    "multiple_sclerosis": "multiple sclerosis",
    "hypertension": "hypertension high blood pressure",
    "diabetes": "diabetes",
    "asthma": "asthma",
    "stroke": "stroke",
    "epilepsy": "epilepsy",
    "depression": "depression",
    "pneumonia": "pneumonia",
    "osteoarthritis": "osteoarthritis",
    "arthritis": "arthritis",
    "heart_failure": "heart failure",
    "atrial_fibrillation": "atrial fibrillation",
    "myocardial_infarction": "myocardial infarction heart attack",
    "parkinsons_disease": "Parkinson disease",
    "alzheimers_disease": "Alzheimer disease",
    "copd": "chronic obstructive pulmonary disease COPD",
    "covid": "COVID-19",
    "influenza": "influenza",
    "anemia": "anemia anaemia",
    "kidney_disease": "chronic kidney disease",
    "reflux": "gastroesophageal reflux",
    "appendicitis": "appendicitis",
    "endometriosis": "endometriosis",
    "rheumatoid_arthritis": "rheumatoid arthritis",
    "back_pain": "back pain low back pain",
    "anxiety_disorder": "anxiety disorder",
}
_INTENT_ENGLISH_TERMS: dict[str, str] = {
    "preparation": "preparation instructions eating drinking smoking fasting before the test",
    "comparison": "differences purpose what tests are included",
    "diagnosis": "diagnosis",
    "treatment": "treatment",
    "recommendations": "guidelines",
    "prevention": "prevention",
    "symptoms": "symptoms",
    "tests": "testing",
    "dosage": "dosage",
}

def _fallback_search_terms(query: str, domain: str | None = None) -> str:
    """Build a concise English search phrase for English-language medical sites.

    Keep the original query for the generic SearXNG pass. For domain-restricted
    fallback searches, explicit English topic and intent terms avoid matching a
    random document merely because common translated words overlap.
    """
    # Russian clinical-guideline catalogs should receive the original Russian
    # query, while English-language sites benefit from an English fallback.
    if domain and domain.lower().endswith(("minzdrav.gov.ru",)):
        return query.strip()

    topics = _topic_ids(query)
    if not topics:
        return query.strip()

    terms: list[str] = []
    for topic in sorted(topics):
        term = _TOPIC_ENGLISH_TERMS.get(topic)
        if term:
            terms.append(term)

    normalized_query = query.casefold().replace("ё", "е")
    if "ct_scan" in topics:
        terms.append("CT scan preparation eating drinking smoking contrast patient instructions")
    if "gastroscopy" in topics:
        terms.append("gastroscopy preparation fasting eating drinking smoking patient instructions")
    if "gastroscopy" in topics and "myocardial_infarction" in topics:
        terms.append(
            "upper gastrointestinal endoscopy after myocardial infarction timing safety sedation "
            "cardiovascular risk antiplatelet anticoagulant clinical guideline"
        )
    if re.search(r"после.{0,35}инфаркт\w*.{0,20}ми[оа]кард\w*|инфаркт\w*.{0,20}ми[оа]кард\w*", normalized_query):
        terms.append("after myocardial infarction endoscopy procedural risk timing sedation")
    if "biochemistry" in topics:
        terms.append("before blood test fasting food smoking patient preparation")
    if "preoperative_tests" in topics:
        terms.append("preoperative blood tests purpose what tests are included")
    if "urology_tests" in topics:
        terms.append("urology investigations urine blood tests purpose")
    if re.search(r"курен|smok", normalized_query):
        terms.append("smoking before test")
    if re.search(r"поест|есть|еда|пищ|eat|food|drink|пить", normalized_query):
        terms.append("eating drinking before procedure")

    intents = _intent_ids(query)
    for intent in sorted(intents):
        term = _INTENT_ENGLISH_TERMS.get(intent)
        if term:
            terms.append(term)

    if re.search(r"взросл|\badult", query, re.IGNORECASE):
        terms.append("adults")
    if not intents:
        terms.append("clinical guidance")
    # Ordered deduplication keeps search requests short and deterministic. Add a
    # quoted phrase after deduplication for condition-specific searches: word-level
    # deduplication otherwise separates "after myocardial infarction" and harms recall.
    result = " ".join(dict.fromkeys(" ".join(terms).split()))
    if re.search(r"после.{0,35}инфаркт\w*.{0,20}ми[оа]кард\w*|инфаркт\w*.{0,20}ми[оа]кард\w*", normalized_query):
        result += ' "after myocardial infarction"'
    return result


def _stem_token(token: str) -> str:
    token = token.lower()
    if re.fullmatch(r"[а-яё]+", token):
        for suffix in _RUSSIAN_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[: -len(suffix)]
        return token
    if re.fullmatch(r"[a-z]+", token):
        for suffix in _ENGLISH_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[: -len(suffix)]
    return token


def _meaningful_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _TOKEN_RE.findall(unquote(text).lower()):
        if raw in _STOP_WORDS or len(raw) < 4:
            continue
        stem = _stem_token(raw)
        if stem in _STOP_WORDS or any(stem.startswith(prefix) for prefix in _GENERIC_PREFIXES):
            continue
        terms.add(stem)
    return terms


def _topic_ids(text: str) -> set[str]:
    normalized = unquote(text).lower().replace("_", " ").replace("-", " ")
    return {
        topic
        for topic, patterns in _COMPILED_TOPIC_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    }


def _intent_ids(text: str) -> set[str]:
    normalized = unquote(text).lower().replace("_", " ").replace("-", " ")
    return {
        intent
        for intent, patterns in _COMPILED_INTENT_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    }


def is_relevant_web_result(query: str, result: WebSearchResult) -> bool:
    """Conservatively reject safe-but-off-topic pages before answer generation.

    Domain allowlisting only establishes source safety, not subject relevance.
    Recognized medical-topic families must occur in both query and source. For
    other topics, require overlap between meaningful non-boilerplate terms.
    """
    if not query.strip():
        return False

    source_text = f"{result.title}\n{unquote(result.url)}\n{result.snippet}"
    if is_weather_query(query):
        assessment = classify_source_relevance(
            query,
            title=result.title,
            url=result.url,
            content=result.snippet,
            source_type="web",
        )
        return assessment.label == "relevant"

    query_topics = _topic_ids(query)
    query_intents = _intent_ids(query)
    source_topics = _topic_ids(source_text)
    source_intents = _intent_ids(source_text)
    # A biochemistry question must not be answered from a generic CBC/complete blood
    # count page just because both mention blood. Keep specific laboratory classes distinct.
    if (
        "biochemistry" in query_topics
        and "biochemistry" not in source_topics
        and "preparation" in query_intents
    ):
        return False
    if query_topics:
        topic_matches = query_topics.intersection(source_topics)
        if not topic_matches:
            return False
        # Do not answer a high-risk patient-specific query from a generic procedure page.
        # When the query explicitly names a recent/previous condition, the result must
        # mention that condition as well as the procedure; routine prep is not evidence
        # about timing, sedation, or safety after a myocardial infarction/stroke.
        required_context_topics = query_topics.intersection({
            "myocardial_infarction", "stroke", "diabetes", "heart_failure",
            "atrial_fibrillation", "pregnancy",
        })
        procedure_topics = query_topics.intersection({
            "gastroscopy", "ct_scan", "mri_scan", "colonoscopy", "ultrasound",
        })
        required_specific_topics = required_context_topics | (procedure_topics if required_context_topics else set())
        if required_context_topics and not required_specific_topics.issubset(source_topics):
            return False
        # A comparison request is answered by combining evidence about its components;
        # individual authoritative pages do not need to contain the word "difference".
        if "comparison" not in query_intents and query_intents and not query_intents.intersection(source_intents):
            return False
        # For procedure-preparation queries require both the named procedure and a
        # concrete preparation cue in the source body. A page merely listing CT among
        # unrelated tests is not an answer.
        if "preparation" in query_intents:
            preparation_problem = preparation_evidence_problem(
                query,
                title=result.title,
                section="",
                content=source_text,
            )
            if preparation_problem:
                return False
        return True

    query_terms = _meaningful_terms(query)
    source_terms = _meaningful_terms(source_text)
    if not query_terms:
        return False
    overlap = query_terms & source_terms
    required = 2 if len(query_terms) >= 5 else 1
    if len(overlap) < required:
        return False
    if query_intents and not query_intents.intersection(source_intents):
        return False
    return True


def has_answerable_web_evidence(query: str, result: WebSearchResult) -> bool:
    """Check whether the fetched body contains usable evidence for the query.

    This is a retrieval-time check, not a medical review of the generated answer.
    It deliberately relies on the result body/snippet rather than allowing the title
    or URL alone to make an otherwise empty page appear answerable.
    """
    body = re.sub(r"\s+", " ", unquote(str(result.snippet or ""))).strip()
    if is_weather_query(query):
        assessment = classify_source_relevance(
            query,
            title=result.title,
            url=result.url,
            content=body,
            source_type="web",
        )
        has_weather_detail = bool(
            re.search(
                r"\d\s*°\s*[cс]?|температур|осадк|ветер|порыв|humidity|precipitation|"
                r"wind speed|feels like|feels-like|forecast for|прогноз на",
                body,
                re.IGNORECASE,
            )
        )
        return assessment.label == "relevant" and len(body) >= 25 and has_weather_detail

    if len(body) < 80:
        return False

    query_topics = _topic_ids(query)
    body_topics = _topic_ids(body)
    if (
        "biochemistry" in query_topics
        and "biochemistry" not in body_topics
        and "preparation" in _intent_ids(query)
    ):
        return False
    if query_topics and not query_topics.intersection(body_topics):
        return False

    # The information type is checked across the complete result by
    # `is_relevant_web_result`; the fetched body may contain the answer without
    # repeating words such as "diagnosis" or "recommendation" in every paragraph.

    # For unknown topics, require actual terms from the question in the content,
    # not just in navigation/title metadata. Known topic+intent pairs are already
    # specific enough once both are present in the body.
    if not query_topics:
        query_terms = _meaningful_terms(query)
        body_terms = _meaningful_terms(body)
        required_overlap = 2 if len(query_terms) >= 5 else 1
        if len(query_terms & body_terms) < required_overlap:
            return False

    # Reject common search-page boilerplate when it has no evidence-bearing detail.
    non_boilerplate = re.sub(
        r"(?i)(home|you are here|back to top|cookie policy|privacy policy|read more|learn more|"
        r"search result snippet|site navigation|all rights reserved)",
        " ", body,
    )
    return len(re.sub(r"[^a-zа-яё0-9]", "", non_boilerplate, flags=re.I)) >= 60


def _metadata_may_be_relevant(query: str, result: WebSearchResult) -> bool:
    """Pre-filter only obvious mismatches before fetching the safe page.

    Metadata is often just a short search snippet. For recognized conditions,
    absence of the condition or requested intent in metadata is ambiguous, not a
    rejection: the full page may still contain the relevant section. A different
    explicitly identified condition or a clearly different intent is a mismatch.
    """
    source_text = f"{result.title}\n{unquote(result.url)}\n{result.snippet}"
    if is_weather_query(query):
        return classify_source_relevance(
            query,
            title=result.title,
            url=result.url,
            content=result.snippet,
            source_type="web",
        ).label != "irrelevant"

    query_topics = _topic_ids(query)
    source_topics = _topic_ids(source_text)
    query_intents = _intent_ids(query)
    source_intents = _intent_ids(source_text)

    if query_topics:
        if source_topics and not query_topics.intersection(source_topics):
            return False
        if (
            query_topics.intersection(source_topics)
            and query_intents
            and source_intents
            and not query_intents.intersection(source_intents)
        ):
            return False
        return True

    query_terms = _meaningful_terms(query)
    source_terms = _meaningful_terms(source_text)
    if query_terms and source_terms and not (query_terms & source_terms):
        return False
    if (
        query_intents
        and source_intents
        and not query_intents.intersection(source_intents)
    ):
        return False
    return True


class _HTMLTextExtractor(HTMLParser):
    """Extract page text while preferring the main/article content over site chrome."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "aside"}
    _CONTENT_IDS = {
        "main-content", "main-content-wrapper", "content", "page-content",
        "primary-content", "article-content",
    }

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._tag_stack: list[tuple[str, bool]] = []
        self.parts: list[str] = []
        self.content_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        attr_map = {key.lower(): (value or "").lower() for key, value in attrs}
        is_content = (
            normalized_tag in {"main", "article"}
            or attr_map.get("role") == "main"
            or attr_map.get("id") in self._CONTENT_IDS
        )
        if normalized_tag in self._SKIP_TAGS:
            self._skip_depth += 1
        # Keep all tags (not just content containers), so a nested <div> closing
        # cannot accidentally terminate an outer id="main-content" region.
        self._tag_stack.append((normalized_tag, is_content))

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        # Pop the matching element and its descendants. This is resilient to
        # malformed HTML while preserving the actual main-content boundary.
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index][0] == normalized_tag:
                del self._tag_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)
                if any(is_content for _, is_content in self._tag_stack):
                    self.content_parts.append(text)


def _extract_html_text(html: str, max_chars: int) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    # A main/article region is substantially more useful for medical evidence
    # than a page's navigation, cookie notices, footer, and overview boilerplate.
    preferred_parts = parser.content_parts if parser.content_parts else parser.parts
    text = " ".join(preferred_parts)
    return text[:max_chars].strip()


def _preferred_evidence_url(query: str, result: WebSearchResult) -> WebSearchResult:
    """Prefer the actual NICE recommendations chapter over a generic guideline landing page.

    NICE landing pages mainly describe the scope and update history. Those pages
    often pass topical filtering but do not contain the diagnostic thresholds needed
    for a clinically grounded answer. The chapter URL stays on the same allowlisted
    HTTPS host; redirects remain disabled during fetching.
    """
    parsed = urlparse(result.url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    match = re.fullmatch(r"/guidance/([a-z]+\d+)", path, re.IGNORECASE)
    requested_intents = _intent_ids(query)
    needs_detail = bool(
        requested_intents.intersection(
            {"diagnosis", "recommendations", "symptoms", "tests", "treatment", "prevention", "dosage"}
        )
    )
    if (
        hostname in {"nice.org.uk", "www.nice.org.uk"}
        and match
        and needs_detail
    ):
        preferred_path = f"/guidance/{match.group(1).lower()}/chapter/recommendations"
        preferred_url = parsed._replace(path=preferred_path, params="", query="", fragment="").geturl()
        return WebSearchResult(
            title=result.title,
            url=preferred_url,
            snippet=result.snippet,
            rank=result.rank,
            domain=result.domain,
            verification_status=result.verification_status,
            verification_note=result.verification_note,
        )
    return result



_DINING_QUERY_RE = re.compile(
    r"\b(?:поесть|покушать|перекус\w*|питани\w*|кафе|кофе|ресторан\w*|фудкорт\w*|"
    r"столов\w*|кофейн\w*|где\s+поесть|места\s+для\s+питания|food|restaurant\w*|"
    r"cafe|cafes|coffee\s+shop|eat\s+near)\b",
    re.IGNORECASE,
)


def is_dining_query(query: str) -> bool:
    """Identify local food-place discovery so it can use an appropriate safe allowlist."""
    return bool(_DINING_QUERY_RE.search(query or ""))


def _broad_search_queries(query: str) -> list[str]:
    """Return short English query variants when the original search is low-recall.

    These are *additional* public-search queries, not replacements for the user's
    wording. Keep condition-specific context in the query when it affects safety.
    """
    topics = _topic_ids(query)
    intents = _intent_ids(query)
    values: list[str] = []

    translated = _fallback_search_terms(query)
    if translated and not re.search(r"[а-яё]", translated, re.IGNORECASE):
        values.append(translated)

    topic_terms = [_TOPIC_ENGLISH_TERMS[item] for item in sorted(topics) if item in _TOPIC_ENGLISH_TERMS]
    intent_terms = [_INTENT_ENGLISH_TERMS[item] for item in sorted(intents) if item in _INTENT_ENGLISH_TERMS]
    normalized = " ".join([*topic_terms, *intent_terms]).strip()
    if normalized:
        values.append(normalized)

    normalized_query = (query or "").casefold().replace("ё", "е")
    if "migraine" in topics and ("diagnosis" in intents or "recommendations" in intents):
        values.extend((
            "migraine diagnosis adults clinical practice guideline",
            "migraine diagnostic criteria adults NICE guideline",
        ))
    if "blood_test" in topics and "preparation" in intents:
        values.extend((
            "complete blood count preparation patient instructions fasting",
            "CBC blood test preparation official patient guidance",
        ))
    if "gastroscopy" in topics and "preparation" in intents:
        if "myocardial_infarction" in topics:
            values.extend((
                "gastroscopy preparation after myocardial infarction procedural safety",
                "upper endoscopy after myocardial infarction sedation clinical guidance",
            ))
        else:
            values.extend((
                "gastroscopy preparation before procedure patient instructions",
                "upper endoscopy preparation NHS patient guidance",
            ))

    original = " ".join((query or "").split())
    output: list[str] = []
    seen: set[str] = {original.casefold()}
    for value in values:
        clean = " ".join(value.split())
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean[:240])
    return output[:5]


class SearXNGWebSearchClient:
    """Local SearXNG adapter with both safety and query-relevance filtering."""

    def __init__(self) -> None:
        self.settings = get_settings()
        configured = {
            x.strip().lower()
            for x in self.settings.web_safe_domains.split(",")
            if x.strip()
        }
        # An environment override may extend the allowlist, but must not silently
        # remove vetted public medical sources required by procedure-preparation fallback.
        self.allowed_domains = (
            configured
            | DEFAULT_SAFE_DOMAINS
            | WEATHER_SAFE_DOMAINS
            | LOCAL_DISCOVERY_SAFE_DOMAINS
        )
        self.authority_domains = tuple(
            x.strip().lower()
            for x in self.settings.web_fallback_domains.split(",")
            if x.strip()
        )

    def _request(self, query: str, timeout: int) -> list[dict] | None:
        try:
            response = requests.get(
                f"{self.settings.searxng_url.rstrip('/')}/search",
                params={
                    "q": query[:600],
                    "format": "json",
                    "language": (
                        "ru" if any(domain in query.lower() for domain in ("minzdrav.gov.ru", "cr.minzdrav.gov.ru"))
                        else "en" if query.lstrip().lower().startswith("site:") or not re.search(r"[а-яё]", query, re.IGNORECASE)
                        else self.settings.web_search_language
                    ),
                    "safesearch": 1,
                    "categories": "general",
                },
                headers={"Accept": "application/json"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            return None
        except ValueError:
            return None

        raw = payload.get("results", [])
        if not isinstance(raw, list):
            return []
        return raw

    def _parse_safe_results(
        self, raw: list[dict], start_rank: int = 1, limit: int = 15
    ) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        seen_urls: set[str] = set()

        for provider_rank, item in enumerate(raw, start=start_rank):
            if not isinstance(item, dict):
                continue

            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls or not is_safe_domain(url, self.allowed_domains):
                continue

            domain = (urlparse(url).hostname or "").lower()
            results.append(
                WebSearchResult(
                    title=str(item.get("title") or domain),
                    url=url,
                    snippet=str(
                        item.get("content")
                        or item.get("snippet")
                        or item.get("description")
                        or ""
                    ),
                    rank=provider_rank,
                    domain=domain,
                )
            )
            seen_urls.add(url)
            if len(results) >= limit:
                break

        return results

    def _enrich_results(
        self, results: list[WebSearchResult], query: str = ""
    ) -> list[WebSearchResult]:
        enriched: list[WebSearchResult] = []
        for result in results:
            # Prefer a content-bearing NICE chapter when search returns its overview.
            # This keeps clinical evidence rather than guideline metadata in the prompt.
            result = _preferred_evidence_url(query, result)
            # Only fetch URLs that already passed the HTTPS + allowlist checks.
            # Never follow redirects; this prevents redirect-based allowlist bypasses.
            try:
                response = requests.get(
                    result.url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": "MedTrust/1.0 local research client",
                    },
                    timeout=self.settings.web_search_fallback_timeout_seconds,
                    verify=True,
                    allow_redirects=False,
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "html" in content_type or not content_type:
                    page_limit = max(1, int(self.settings.web_source_max_chars))
                    parsed_url = urlparse(result.url)
                    if (
                        (parsed_url.hostname or "").lower() in {"nice.org.uk", "www.nice.org.uk"}
                        and "/chapter/recommendations" in parsed_url.path.lower()
                    ):
                        # Existing .env files may still specify 6000 characters. A
                        # recommendation chapter needs more room than a landing page
                        # to retain assessment, diagnosis, aura and red-flag sections.
                        page_limit = max(page_limit, 14000)
                    page_text = _extract_html_text(response.text, page_limit)
                    if page_text:
                        # Keep page content first and reserve space for a focused
                        # SearXNG snippet. Always cap the final evidence block, even
                        # when the search provider returns an unusually long snippet.
                        search_snippet = result.snippet.strip()
                        marker = "\n\nSearch result snippet: "
                        if search_snippet and search_snippet.casefold() not in page_text.casefold():
                            snippet_budget = min(
                                len(search_snippet), max(0, page_limit - len(marker)), page_limit // 3
                            )
                            body_budget = max(0, page_limit - len(marker) - snippet_budget)
                            combined_text = (
                                page_text[:body_budget].rstrip()
                                + marker
                                + search_snippet[:snippet_budget]
                            )[:page_limit]
                        else:
                            combined_text = page_text[:page_limit]
                        result = WebSearchResult(
                            title=result.title,
                            url=result.url,
                            snippet=combined_text,
                            rank=result.rank,
                            domain=result.domain,
                            verification_status=result.verification_status,
                            verification_note=result.verification_note,
                        )
            except (requests.RequestException, UnicodeError):
                # If the page cannot be fetched, use the SearXNG snippet, but it
                # still has to pass the exact same relevance check afterwards.
                pass
            enriched.append(result)
        return enriched

    @staticmethod
    def _plausibly_related_for_unverified(query: str, result: WebSearchResult) -> bool:
        """Allow a safe same-topic page as provisional evidence when strict checks fail.

        Do not loosen the condition-and-procedure pair for high-risk queries such as
        endoscopy after myocardial infarction. A broad topic match is only enough to
        preserve a link with an explicit unverified label, never to pass source checks.
        """
        source_text = f"{result.title} {unquote(result.url)} {result.snippet}"
        query_topics = _topic_ids(query)
        source_topics = _topic_ids(source_text)
        if query_topics:
            if not query_topics.intersection(source_topics):
                return False
            risk_context_topics = query_topics.intersection({
                "myocardial_infarction", "stroke", "diabetes", "heart_failure",
                "atrial_fibrillation", "pregnancy",
            })
            procedure_topics = query_topics.intersection({
                "gastroscopy", "ct_scan", "mri_scan", "colonoscopy", "ultrasound",
            })
            if risk_context_topics and procedure_topics:
                return (risk_context_topics | procedure_topics).issubset(source_topics)
            return True

        query_terms = _meaningful_terms(query)
        source_terms = _meaningful_terms(source_text)
        return bool(query_terms.intersection(source_terms))

    def _relevant_and_enriched(
        self,
        query: str,
        candidates: list[WebSearchResult],
        max_fetch: int = 10,
    ) -> list[WebSearchResult]:
        # First remove only explicit contradictions. Do not reject an otherwise
        # safe page merely because its short title/snippet omits the query intent.
        viable = [item for item in candidates if _metadata_may_be_relevant(query, item)]
        viable = [_preferred_evidence_url(query, item) for item in viable]
        viable.sort(
            key=lambda item: (not is_relevant_web_result(query, item), item.rank)
        )
        enriched = self._enrich_results(viable[:max(1, max_fetch)], query=query)
        confirmed: list[WebSearchResult] = []
        provisional: list[WebSearchResult] = []
        for item in enriched:
            strong_match = (
                is_relevant_web_result(query, item)
                and has_answerable_web_evidence(query, item)
            )
            if strong_match:
                confirmed.append(item)
                continue
            if self._plausibly_related_for_unverified(query, item):
                provisional.append(WebSearchResult(
                    title=item.title,
                    url=item.url,
                    snippet=item.snippet,
                    rank=item.rank,
                    domain=item.domain,
                    verification_status="unverified",
                    verification_note=(
                        "Тема страницы совпадает с запросом, но проверка не подтвердила все условия/утверждения. "
                        "Использовать только как предварительный материал и проверить вручную."
                    ),
                ))
        # Confirmed evidence always precedes provisional pages. Provisional results
        # remain visible so later answer logic can give a cautious answer and expose
        # the actual URL rather than converting a relevant but imperfect page to no result.
        return sorted(confirmed, key=lambda item: item.rank) + sorted(
            provisional, key=lambda item: item.rank
        )

    def search(self, query: str, limit: int = 3) -> WebSearchResponse:
        if not self.settings.web_search_enabled:
            return WebSearchResponse("disabled", [])

        requested_limit = max(1, min(limit, 3))
        candidate_limit = min(30, max(15, requested_limit * 10))
        any_request_completed = False
        provider_returned_results = False
        safe_results_seen = False
        pool: list[WebSearchResult] = []
        seen_urls: set[str] = set()
        attempted_queries: list[str] = []

        def gather(search_query: str, timeout: int, use_original_query_for_relevance: bool = True) -> None:
            nonlocal any_request_completed, provider_returned_results, safe_results_seen
            attempted_queries.append(search_query)
            raw = self._request(search_query, timeout)
            if raw is None:
                return
            any_request_completed = True
            provider_returned_results = provider_returned_results or bool(raw)
            parsed = self._parse_safe_results(raw, limit=candidate_limit)
            safe_results_seen = safe_results_seen or bool(parsed)
            unique = [item for item in parsed if item.url not in seen_urls]
            seen_urls.update(item.url for item in parsed)
            if not unique:
                return
            relevance_query = query if use_original_query_for_relevance else search_query
            pool.extend(self._relevant_and_enriched(
                relevance_query, unique, max_fetch=max(12, requested_limit * 4)
            ))

        # Primary attempt uses the user's original language and wording.
        gather(query, self.settings.web_search_timeout_seconds)
        if sum(item.verification_status == "verified" for item in pool) < requested_limit:
            # If a long Russian query produces no results (or only weak results), retry
            # with concise English equivalents *without* a site: restriction. This is
            # important because site-restricted fallback alone can suppress valid hits.
            for variant in _broad_search_queries(query):
                gather(variant, self.settings.web_search_fallback_timeout_seconds)
                if sum(item.verification_status == "verified" for item in pool) >= requested_limit:
                    break

        # Use domain-specific searches as a final recall path, while retaining weak
        # same-topic pages found earlier as provisional sources.
        normalized_query = query.casefold().replace("ё", "е")
        preparation_or_lab_query = bool(
            _topic_ids(query) & {"ct_scan", "gastroscopy", "biochemistry", "blood_test", "preoperative_tests", "urology_tests"}
        ) or bool(re.search(r"подготов\w*|натощак|поест|курен|предоперацион|урологическ|biochemical|preoperative|urinalysis", normalized_query))
        if is_weather_query(query):
            fallback_domains = ("gismeteo.ru", "meteoinfo.ru", "rp5.ru", "weather.com", "meteoblue.com")
        elif is_dining_query(query):
            fallback_domains = tuple(sorted(LOCAL_DISCOVERY_SAFE_DOMAINS))
        elif preparation_or_lab_query:
            topics = _topic_ids(query)
            if "ct_scan" in topics or "gastroscopy" in topics or "mri" in topics:
                medical_preparation_domains = (
                    "radiologyinfo.org", "nhs.uk", "medlineplus.gov", "cr.minzdrav.gov.ru",
                    "cancer.gov", "mayoclinic.org", "msdmanuals.com", "nice.org.uk",
                )
            else:
                medical_preparation_domains = (
                    "medlineplus.gov", "labtestsonline.org.uk", "testing.com", "nhs.uk",
                    "cr.minzdrav.gov.ru", "mayoclinic.org", "msdmanuals.com",
                    "pubmed.ncbi.nlm.nih.gov", "who.int",
                )
            fallback_domains = tuple(dict.fromkeys((*medical_preparation_domains, *self.authority_domains)))
        else:
            fallback_domains = self.authority_domains

        verified_domains = {
            item.domain for item in pool if item.verification_status == "verified"
        }
        configured_max_domains = max(1, self.settings.web_fallback_max_domains)
        max_domains = min(10, max(configured_max_domains, 10 if preparation_or_lab_query else configured_max_domains))
        for domain in fallback_domains[:max_domains]:
            if len(verified_domains) >= requested_limit:
                break
            fallback_terms = _fallback_search_terms(query, domain)
            fallback_query = f"site:{domain} {fallback_terms}"
            gather(fallback_query, self.settings.web_search_fallback_timeout_seconds)
            # `gather` applies the original query's relevance checks. Do not stop on a
            # merely provisional result; keep searching for a better confirmed source.
            verified_domains = {
                item.domain for item in pool if item.verification_status == "verified"
            }

        # Deduplicate by URL, preferring a verified instance if the same page was found
        # through multiple query variants. Then favour confirmed material and domain
        # diversity before filling the remaining slots with provisional sources.
        by_url: dict[str, WebSearchResult] = {}
        for item in pool:
            key = item.url.rstrip("/").casefold()
            existing = by_url.get(key)
            if existing is None or (
                existing.verification_status != "verified" and item.verification_status == "verified"
            ):
                by_url[key] = item
        ordered = sorted(
            by_url.values(),
            key=lambda item: (item.verification_status != "verified", item.rank, item.domain),
        )
        selected: list[WebSearchResult] = []
        used_domains: set[str] = set()
        for item in ordered:
            if item.domain not in used_domains:
                selected.append(item)
                used_domains.add(item.domain)
            if len(selected) >= requested_limit:
                break
        if len(selected) < requested_limit:
            selected_urls = {item.url for item in selected}
            for item in ordered:
                if item.url not in selected_urls:
                    selected.append(item)
                    selected_urls.add(item.url)
                if len(selected) >= requested_limit:
                    break

        if selected:
            return WebSearchResponse("success", selected, attempted_queries=attempted_queries)
        if safe_results_seen:
            return WebSearchResponse("no_relevant_results", [], attempted_queries=attempted_queries)
        if provider_returned_results:
            return WebSearchResponse("no_safe_results", [], attempted_queries=attempted_queries)
        if not any_request_completed:
            return WebSearchResponse("api_error", [], attempted_queries=attempted_queries)
        return WebSearchResponse("no_provider_results", [], attempted_queries=attempted_queries)


# Keep a stable service name for future provider swaps.
WebSearchClient = SearXNGWebSearchClient
