"""Deterministic, inspectable source-relevance scoring for Wiki and web results.

This is a retrieval aid, not a correctness or safety validator. It never decides
whether the model may answer; it helps prioritize supporting material and avoid
obviously unrelated context.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from urllib.parse import unquote


_WEATHER_RE = re.compile(
    r"погод\w*|прогноз\w*|температур\w*|осадк\w*|ветер(?:ом|а|у|е|ы)?\b|влажност\w*|"
    r"weather|forecast|temperature|precipitation|humidity|wind(?:y)?",
    re.IGNORECASE,
)
_WEATHER_WORDS = {
    "погод", "прогноз", "температур", "осадк", "ветер", "влажност",
    "weather", "forecast", "temperature", "precipitation", "humidity", "wind",
}
# Query-language aliases help match Russian city names to English-language
# weather providers without relying on exact spelling in a URL or snippet.
_WEATHER_PLACE_ALIASES: dict[str, tuple[str, ...]] = {
    "екатеринбург": ("екатеринбург", "yekaterinburg", "ekaterinburg"),
    "москва": ("москва", "moscow"),
    "санкт петербург": ("санкт петербург", "saint petersburg", "st petersburg", "spb"),
    "новосибирск": ("новосибирск", "novosibirsk"),
    "казань": ("казань", "kazan"),
    "нижний новгород": ("нижний новгород", "nizhny novgorod"),
    "челябинск": ("челябинск", "chelyabinsk"),
    "самара": ("самара", "samara"),
    "омск": ("омск", "omsk"),
    "пермь": ("пермь", "perm"),
    "уфа": ("уфа", "ufa"),
    "красноярск": ("красноярск", "krasnoyarsk"),
    "воронеж": ("воронеж", "voronezh"),
    "краснодар": ("краснодар", "krasnodar"),
    "ростов на дону": ("ростов на дону", "rostov-on-don", "rostov on don"),
    "калининград": ("калининград", "kaliningrad"),
}
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_RUSSIAN_SUFFIXES = tuple(sorted((
    "ирования", "ироваться", "ировать", "иями", "ями", "ами", "ого", "его",
    "ому", "ему", "ыми", "ими", "иях", "аться", "яться", "иться", "еться",
    "ыться", "аться", "яться", "иями", "ах", "ях", "ией", "иям", "ью",
    "ия", "ие", "ые", "ое", "ая", "яя", "ой", "ий", "ый", "ую", "юю",
    "ов", "ев", "ей", "ам", "ям", "ом", "ем", "ок",
    "ть", "ся", "а", "я", "ы", "и", "у", "ю", "е", "о", "ь",
), key=len, reverse=True))
_ENGLISH_SUFFIXES = ("ization", "ations", "ation", "ments", "ment", "ingly", "edly", "ing", "ed", "es", "s")
_STOP_WORDS = {
    "а", "без", "бы", "быть", "в", "во", "вот", "все", "всех", "вы", "где",
    "для", "до", "его", "ее", "её", "если", "же", "за", "и", "из", "или",
    "им", "их", "как", "какая", "какие", "какой", "каком", "когда", "кто",
    "ли", "мне", "мы", "на", "над", "не", "него", "нее", "неё", "ни", "но",
    "о", "об", "один", "одна", "одни", "одного", "одной", "одном", "одну",
    "он", "она", "они", "оно", "от", "по", "под", "при", "про", "с", "со",
    "так", "также", "то", "того", "тоже", "у", "уже", "что", "чтобы", "это",
    "этот", "эта", "эти", "этом", "я", "the", "a", "an", "and", "are", "as",
    "at", "be", "by", "can", "could", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "should", "that", "this", "to", "was",
    "were", "what", "when", "where", "which", "who", "why", "with", "would", "you",
    "your",
}
_GENERIC_QUERY_STEMS = {
    "современ", "актуальн", "новейш", "рекомендац", "диагност", "информац",
    "общ", "взросл", "пациент", "медицин", "вопрос", "данн", "нужн", "можн",
    "подход", "метод", "описан", "сведен", "общ", "информаци", "информац", "general", "information", "current",
    "подскаж", "расскаж", "уточн", "интерес", "хотел", "нужн", "требует", "требован",
    "правил", "услов", "порядок", "процедур", "стоим", "цена", "режим", "работ",
    "контакт", "телефон", "адрес", "место", "местополож", "наход", "располож",
    "рядом", "близко", "ориентир", "маршрут", "проезд", "как добрат", "вход", "выход",
    "паркинг", "парков", "питани", "кафе", "ресторан", "столов", "кофейн", "магазин",
    "услуг", "сервис", "документ", "справк", "заявлен", "оформлен", "оплат", "возврат",
    "врач", "специалист", "запис", "прием", "приём", "консультац", "направлен", "отделен",
    "анализ", "исследован", "диагностик", "лечен", "терап", "препарат", "лекарств",
    "симптом", "признак", "причин", "риск", "осложнен", "противопоказан", "побочн",
    "возраст", "ребен", "ребён", "взросл", "женщин", "мужчин", "беремен", "кормлен",
    "профилактик", "реабилитац", "подготов", "результат", "норм", "показател", "срок",
    "длительност", "частот", "доз", "дозиров", "совместим", "хранен", "применен",
}

_SPECIALTY_PATTERNS: dict[str, str] = {
    "ревматолог": r"ревматолог\w*",
    "кардиолог": r"кардиолог\w*",
    "невролог": r"невролог\w*",
    "эндокринолог": r"эндокринолог\w*",
    "гастроэнтеролог": r"гастроэнтеролог\w*",
    "гинеколог": r"гинеколог\w*",
    "дерматолог": r"дерматолог\w*",
    "уролог": r"уролог\w*",
    "офтальмолог": r"офтальмолог\w*",
    "отоларинголог": r"отоларинголог\w*|лор\b",
    "терапевт": r"терапевт\w*",
    "педиатр": r"педиатр\w*",
    "аллерголог": r"аллерголог\w*",
    "онколог": r"онколог\w*",
    "пульмонолог": r"пульмонолог\w*",
    "травматолог": r"травматолог\w*",
    "хирург": r"хирург\w*",
}

_CONCEPT_PATTERNS: dict[str, str] = {
    # Reception / branch operations
    "parking": r"парков\w*|паркинг|parking|парковочн\w*|машин\w*|автомобил\w*|оставить\s+машин\w*|место\s+для\s+машин\w*",
    "access": r"допуск\w*|доступ\w*|пропуск\w*|шлагбаум\w*|access|entry",
    "address": r"адрес\w*|как\s+добрат\w*|проезд\w*|маршрут\w*|address|directions",
    "schedule": r"режим\w*\s+работ\w*|график\w*|расписани\w*|час\w*\s+работ\w*|opening\s+hours|schedule",
    "contacts": r"контакт\w*|телефон\w*|почт\w*|номер\w*|contacts?|phone|email",
    "pricing": r"стоимост\w*|цен\w*|тариф\w*|рубл\w*|оплат\w*|price|cost|fee|payment",
    "dining": r"кафе\w*|ресторан\w*|столов\w*|кофейн\w*|фудкорт\w*|поест\w*|питан\w*|restaurant|cafe|dining|food",
    "appointment": r"запис\w*|при[её]м\w*|консультац\w*|талон\w*|очеред\w*|appointment|booking",
    "documents": r"документ\w*|справк\w*|полис\w*|паспорт\w*|оформлен\w*|document|certificate|insurance",
    "preparation": r"подготов\w*|натощак|отмен\w*\s+препарат\w*|перед\s+(?:процедур\w*|исследован\w*|анализ\w*)|preparation|fasting",
    "gastroscopy": r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*|gastroscop\w*|upper\s+endoscop\w*",
    "blood_test_preparation": r"анализ\w*\s+кров\w*|сдач\w*\s+кров\w*|кров\w*\s+натощак|общ\w*\s+анализ\w*\s+кров\w*|blood\s+test|complete\s+blood\s+count|cbc",
    "ct_scan": r"(?<![а-яё])кт(?![а-яё])|компьютерн\w*\s+томограф\w*|computed\s+tomograph\w*|\bct\s+scan\b",
    "mri_scan": r"(?<![а-яё])мрт(?![а-яё])|магнитно-резонансн\w*\s+томограф\w*|magnetic\s+resonance\s+imag\w*",
    "ultrasound": r"узи|ультразвуков\w*\s+исследован\w*|ultrasound|sonograph\w*",
    "colonoscopy": r"колоноскоп\w*|colonoscop\w*",
    # Clinical / patient-information topics
    "symptoms": r"симптом\w*|признак\w*|проявлен\w*|жалоб\w*|symptom\w*|signs?",
    "diagnosis": r"диагност\w*|обследован\w*|исследован\w*|анализ\w*|тест\w*|diagnos\w*|examination|test\w*",
    "treatment": r"лечен\w*|терап\w*|тактик\w*|помощ\w*|назначен\w*|treatment|therapy|management",
    "medication": r"лекарств\w*|препарат\w*|дозиров\w*|доз\w*|побочн\w*\s+эффект\w*|medication|drug\w*|dosage|side\s+effects?",
    "contraindications": r"противопоказан\w*|ограничен\w*|нельзя|не\s+рекомендует\w*|contraindication\w*|restriction\w*",
    "prevention": r"профилактик\w*|вакцинац\w*|прививк\w*|предотвращен\w*|prevention|vaccination|immunization",
    "referral": r"направлен\w*|к\s+какому\s+врачу|специалист\w*|врач\w*|referral|specialist|doctor",
    "results": r"результат\w*|расшифров\w*|норм\w*\s+показател\w*|interpretation|reference\s+range|results?",
}

_BRANCH_PATTERNS: dict[str, str] = {
    "садовая": r"садов\w*\s*15?",
    "лесная": r"лесн\w*\s*42?",
    "полевая": r"полев\w*\s*7",
    "строителей": r"строител\w*\s*64?б?",
    "цветочная": r"цветочн\w*\s*20",
    "кленовая": r"кл[её]нов\w*\s*8\s*а?",
    "заводская": r"заводск\w*\s*12",
    "речной": r"жк\s*речн\w*|набережн\w*\s*5\s*/?\s*1?",
}



# Preparation questions need passage-level, procedure-specific evidence. A generic
# word such as "подготовка" must not make a CBC page answer a gastroscopy or CT query.
_PREPARATION_INTENT_RE = re.compile(
    r"подготов\w*|натощак|перед\s+(?:сдач\w*|анализ\w*|исследован\w*|процедур\w*)|"
    r"что\s+(?:можно|нельзя|нужно)\s+(?:делать|есть|пить|принимать)\s+перед|"
    r"before\s+(?:the\s+)?(?:procedure|test|scan)|prepar\w*|fasting|"
    r"can\s+i\s+(?:eat|drink|smoke)|eating\s+and\s+drinking|"
    r"можно\s+ли.{0,100}(?:есть|пить|курить|поесть|покурить).{0,80}перед|"
    r"(?:поесть|покурить|курить).{0,80}перед",
    re.IGNORECASE,
)

_PREPARATION_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("biochemical_blood_test",
     r"биохим\w*.{0,35}(?:анализ\w*\s+кров\w*|кров\w*.{0,20}анализ\w*)|"
     r"biochemical\s+(?:blood\s+)?test|blood\s+chemistry|serum\s+chemistry",
     r"натощак|не\s+менее\s+\d+\s*час|через\s+\d+\s*час|последн\w*\s+при[её]м\w*\s+пищ|"
     r"курен\w*|алкогол\w*|перед\s+сдач|до\s+сдач|подготов\w*|не\s+принимать\s+пищ|"
     r"fasting|hours?\s+before|avoid\s+smoking|smoking|before\s+the\s+test|prepar\w*"),
    ("gastroscopy", r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*|upper\s+endoscop\w*|gastroscop\w*",
     r"натощак|не\s+(?:есть|пить)|не\s+принимать\s+пищ|последн\w*\s+при[её]м\w*\s+пищ|час\w*\s+до|курен\w*|лекарств\w*|анестези\w*|слабител\w*|клизм\w*|fasting|before\s+the\s+procedure|prepar\w*"),
    ("colonoscopy", r"колоноскоп\w*|colonoscop\w*",
     r"очист\w*\s+кишечник|слабител\w*|клизм\w*|безшлаков\w*|диет\w*|препарат\w*\s+для\s+очистк"),
    ("ct_scan", r"(?<![а-яё])кт(?![а-яё])|компьютерн\w*\s+томограф\w*|computed\s+tomograph\w*|\bct\s+scan\b",
     r"контраст\w*|креатинин\w*|\bскф\b|аллерги\w*|металл\w*|имплант\w*|кардиостимулятор\w*|"
     r"мочев\w*\s+пузыр|натощак|не\s+(?:есть|пить)|не\s+принимать\s+пищ|снять\s+(?:металл|украшен)|беремен\w*|"
     r"prepar\w*|before\s+(?:your\s+)?scan|fasting|eat\w*|drink\w*|avoid\s+smoking|smoking|do\s+not\s+eat"),
    ("mri_scan", r"(?<![а-яё])мрт(?![а-яё])|магнитно-резонансн\w*\s+томограф\w*|magnetic\s+resonance\s+imag\w*",
     r"металл\w*|имплант\w*|кардиостимулятор\w*|контраст\w*|аллерги\w*|снять\s+(?:металл|украшен)|беремен\w*|натощак|не\s+(?:есть|пить)"),
    ("ultrasound", r"узи|ультразвуков\w*\s+исследован\w*|ultrasound|sonograph\w*",
     r"натощак|мочев\w*\s+пузыр|наполнен\w*|газообраз\w*|не\s+есть|не\s+пить|слабител\w*|очист\w*\s+кишечник"),
    ("blood_test", r"общ\w*\s+анализ\w*\s+кров\w*|анализ\w*\s+кров\w*|сдач\w*\s+кров\w*|кров\w*\s+натощак|\bоак\b|complete\s+blood\s+count|blood\s+test|\bcbc\b",
     r"натощак|не\s+менее\s+\d+\s*час|через\s+\d+\s*час|последн\w*\s+при[её]м\w*\s+пищ|курен\w*|алкогол\w*|перед\s+сдач|до\s+сдач|подготов\w*|не\s+принимать\s+пищ"),
)


def preparation_evidence_problem(
    query: str,
    *,
    title: str = "",
    path: str = "",
    section: str = "",
    content: str = "",
) -> str | None:
    """Return a diagnostic reason when a source does not answer a named prep facet.

    General preparation terms are not enough: evidence must mention the requested
    procedure and contain a matching preparation instruction. Returns None when this
    specialized guard is not applicable or when passage-level evidence is adequate.
    """
    normalized_query = (query or "").casefold().replace("ё", "е")
    if not _PREPARATION_INTENT_RE.search(normalized_query):
        return None

    target = next((item for item in _PREPARATION_TARGETS if re.search(item[1], normalized_query)), None)
    if target is None:
        return None
    name, target_pattern, cue_pattern = target
    title_section = f"{title} {section}".casefold().replace("ё", "е")
    content_norm = (content or "").casefold().replace("ё", "е")
    contextual_text = f"{section}\n{content}".casefold().replace("ё", "е")
    full_context = f"{title}\n{section}\n{content}".casefold().replace("ё", "е")

    # Avoid confusing similar endoscopy preparation instructions.
    if name == "gastroscopy" and re.search(r"колоноскоп\w*|colonoscop\w*", content_norm) and not re.search(
        r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*|gastroscop\w*", contextual_text
    ):
        return "procedure_mismatch_colonoscopy_vs_gastroscopy"

    if not re.search(target_pattern, full_context):
        return f"requested_procedure_missing:{name}"

    # If the procedure is a section/title, instructions may be in its following body
    # text. If the procedure only appears incidentally within the body (e.g. CT named
    # in a list of radiation studies), require a cue in that same line/sentence.
    heading_scoped = bool(re.search(target_pattern, title_section))
    if heading_scoped:
        has_instruction = bool(re.search(cue_pattern, f"{section}\n{content}", re.IGNORECASE))
    else:
        has_instruction = any(
            re.search(target_pattern, line, re.IGNORECASE)
            and re.search(cue_pattern, line, re.IGNORECASE)
            for line in re.split(r"[\n.!?;]+", content)
        )
    if not has_instruction:
        return f"procedure_specific_preparation_instruction_missing:{name}"
    return None

def _requested_specialty(query: str) -> str | None:
    value = (query or "").casefold().replace("ё", "е")
    return next((name for name, pattern in _SPECIALTY_PATTERNS.items() if re.search(pattern, value)), None)


def _requested_branch(query: str) -> str | None:
    value = (query or "").casefold().replace("ё", "е")
    return next((name for name, pattern in _BRANCH_PATTERNS.items() if re.search(pattern, value)), None)


@dataclass(frozen=True)
class RelevanceAssessment:
    score: float
    label: str
    reason: str
    matched_terms: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        result = asdict(self)
        result["matched_terms"] = list(self.matched_terms)
        return result


def is_weather_query(query: str) -> bool:
    """Identify live-weather intent without mistaking clinical body temperature for weather."""
    value = (query or "").strip().lower().replace("ё", "е")
    if not value:
        return False
    clinical_temperature = bool(re.search(
        r"температур\w*\s+(?:тела|пациент|ребен|ребён|больн|человек)|"
        r"(?:температур\w*\s+при\s+(?:простуд|грипп|инфекц)|лихорадк|жаропонижа)",
        value,
    ))
    if clinical_temperature:
        return False
    explicit_weather = bool(re.search(
        r"погод\w*|прогноз\w*|осадк\w*|ветер(?:ом|а|у|е|ы)?\b|влажност\w*|"
        r"weather|forecast|precipitation|humidity|wind(?:y)?",
        value,
        re.IGNORECASE,
    ))
    if explicit_weather:
        return True
    # Temperature-only phrasing is weather-related when a place or outdoor context
    # is present, not when asking about a symptom or a patient's temperature.
    has_temperature = bool(re.search(r"температур\w*|temperature", value, re.IGNORECASE))
    has_place = any(
        city in value or any(alias in value for alias in aliases)
        for city, aliases in _WEATHER_PLACE_ALIASES.items()
    )
    return has_temperature and (has_place or bool(re.search(r"на улице|за окном|outside", value)))


def _stem(token: str) -> str:
    token = token.casefold().replace("ё", "е")
    # High-frequency noun/verb variants where a naive suffix strip is misleading
    # (e.g. "допуска" must match "допуск", and "подготовке" match "подготовиться").
    for prefix, normalized in (
        ("подготовк", "подготов"), ("подготов", "подготов"),
        ("парковк", "парков"), ("парков", "парков"),
        ("допуск", "допуск"), ("доступ", "доступ"),
    ):
        if token.startswith(prefix):
            return normalized
    if re.fullmatch(r"[а-я]+", token):
        for suffix in _RUSSIAN_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[:-len(suffix)]
    elif re.fullmatch(r"[a-z]+", token):
        for suffix in _ENGLISH_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[:-len(suffix)]
    return token


def _tokens(text: str) -> list[str]:
    return [_stem(token) for token in _TOKEN_RE.findall(unquote(text or "").lower())]


# Clinical intent words describe what the user wants to know, not the disease or
# condition itself. Treat stem variants consistently ("диагностике" -> "диагностик")
# so they cannot accidentally count as topic-specific evidence.
_GENERIC_TOPIC_PREFIXES = (
    "современн", "актуальн", "последн", "новейш", "рекомендац", "диагност",
    "обследован", "исследован", "анализ", "тест", "лечен", "терап", "симптом",
    "признак", "профилактик", "противопоказан", "доз", "побочн", "медицин",
    "взросл", "пациент", "вопрос", "информац", "данн", "метод", "подход",
    "клиническ", "клиник", "врач", "специалист", "прием", "запис", "результат",
    "показател", "применен", "recommend", "guideline", "diagnos", "treat", "therap",
    "symptom", "prevention", "contraindication", "dosage", "side", "effect",
    "adult", "patient", "medical", "current", "latest", "recent", "modern",
)
_CONTEXT_ONLY_PREFIXES = (
    "взросл", "ребен", "ребён", "пациент", "мужчин", "женщин", "adult", "patient",
)
_CLINICAL_INTENT_GROUPS: tuple[tuple[str, str], ...] = (
    (
        r"рекомендац\w*|руководств\w*|клиническ\w*\s+рекомендац\w*|guideline\w*|recommendation\w*",
        r"рекомендац\w*|руководств\w*|клиническ\w*\s+рекомендац\w*|guideline\w*|recommendation\w*",
    ),
    (
        r"диагност\w*|обследован\w*|диагноз\w*|diagnos\w*|examination|testing",
        r"диагност\w*|обследован\w*|диагноз\w*|diagnos\w*|examination|testing",
    ),
    (
        r"лечен\w*|терап\w*|management|treatment|therap\w*",
        r"лечен\w*|терап\w*|management|treatment|therap\w*",
    ),
    (
        r"симптом\w*|признак\w*|проявлен\w*|symptom\w*|clinical\s+features?",
        r"симптом\w*|признак\w*|проявлен\w*|symptom\w*|clinical\s+features?",
    ),
    (
        r"профилактик\w*|предотвращен\w*|prevention|prevent\w*",
        r"профилактик\w*|предотвращен\w*|prevention|prevent\w*",
    ),
    (
        r"противопоказан\w*|побочн\w*|доз\w*|дозиров\w*|contraindication\w*|side\s+effects?|dosage|dose\b",
        r"противопоказан\w*|побочн\w*|доз\w*|дозиров\w*|contraindication\w*|side\s+effects?|dosage|dose\b",
    ),
)
_CLINICAL_INTENT_RE = re.compile(
    r"рекомендац\w*|руководств\w*|клиническ\w*\s+рекомендац\w*|guideline\w*|recommendation\w*|"
    r"диагност\w*|обследован\w*|диагноз\w*|diagnos\w*|"
    r"лечен\w*|терап\w*|management|treatment|therap\w*|"
    r"симптом\w*|признак\w*|проявлен\w*|symptom\w*|"
    r"профилактик\w*|предотвращен\w*|prevention|prevent\w*|"
    r"противопоказан\w*|побочн\w*|доз\w*|дозиров\w*|contraindication\w*|side\s+effects?|dosage|dose\b",
    re.IGNORECASE,
)
_CLINICAL_TOPIC_PATTERNS: dict[str, str] = {
    "migraine": r"мигрен\w*|migrain\w*",
    "gastroscopy": r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*|gastroscop\w*|upper\s+endoscop\w*|esophagogastroduodenoscop\w*",
    "myocardial_infarction": r"инфаркт\w*\s+ми[оа]кард\w*|myocardial\s+infarction|heart\s+attack",
    "stroke": r"инсульт\w*|stroke\w*",
    "diabetes": r"сахарн\w*\s+диабет\w*|diabet\w*",
    "heart_failure": r"сердечн\w*\s+недостаточност\w*|heart\s+failure",
    "atrial_fibrillation": r"фибрилляц\w*\s+предсерд\w*|atrial\s+fibrillation",
    "ct_scan": r"(?<![а-яё])кт(?![а-яё])|компьютерн\w*\s+томограф\w*|computed\s+tomograph\w*|\bct\s+scan\b",
    "mri_scan": r"(?<![а-яё])мрт(?![а-яё])|магнитно-резонансн\w*\s+томограф\w*|magnetic\s+resonance",
    "colonoscopy": r"колоноскоп\w*|colonoscop\w*",
    "ultrasound": r"узи|ультразвуков\w*\s+исследован\w*|ultrasound",
}

_FRESHNESS_RE = re.compile(
    r"современн\w*|актуальн\w*|последн\w*|новейш\w*|на\s+сегодняшний\s+день|"
    r"current|latest|recent|up[- ]to[- ]date|newest|modern",
    re.IGNORECASE,
)


def _is_generic_topic_token(token: str) -> bool:
    if not token or token in _STOP_WORDS:
        return True
    return any(token.startswith(prefix) for prefix in _GENERIC_TOPIC_PREFIXES)


def _specific_topic_tokens(query: str) -> set[str]:
    return {
        token for token in _tokens(query)
        if len(token) >= 4
        and not _is_generic_topic_token(token)
        and not any(token.startswith(prefix) for prefix in _CONTEXT_ONLY_PREFIXES)
    }


def requires_topic_specific_clinical_evidence(query: str) -> bool:
    """Whether a clinical-knowledge query needs condition-specific source evidence."""
    return bool(_CLINICAL_INTENT_RE.search(query or "") and _specific_topic_tokens(query))


def requires_fresh_clinical_search(query: str) -> bool:
    """Force online verification when the user explicitly asks for current guidance."""
    value = query or ""
    return bool(
        requires_topic_specific_clinical_evidence(value)
        and _FRESHNESS_RE.search(value)
        and re.search(r"рекомендац\w*|руководств\w*|guideline\w*|recommendation\w*", value, re.IGNORECASE)
    )


def has_topic_specific_clinical_evidence(query: str, source_text: str) -> bool:
    """Require a source to mention the requested clinical topic and intent.

    The topic check is bilingual: a Russian question about migraine may be answered
    by an English-language NICE/medical source. Patient-risk context is stricter: if
    the query names a previous infarction/stroke or another major condition, that
    condition and the procedure must both be present in the source text.
    """
    if not requires_topic_specific_clinical_evidence(query):
        return True
    query_value = (query or "").casefold().replace("ё", "е")
    source_value = (source_text or "").casefold().replace("ё", "е")
    query_topics = {
        topic for topic, pattern in _CLINICAL_TOPIC_PATTERNS.items()
        if re.search(pattern, query_value, re.IGNORECASE)
    }
    source_topics = {
        topic for topic, pattern in _CLINICAL_TOPIC_PATTERNS.items()
        if re.search(pattern, source_value, re.IGNORECASE)
    }
    if query_topics:
        context_topics = query_topics.intersection({
            "myocardial_infarction", "stroke", "diabetes", "heart_failure", "atrial_fibrillation"
        })
        if context_topics:
            if not query_topics.issubset(source_topics):
                return False
        elif not query_topics.intersection(source_topics):
            return False
    else:
        topic_tokens = _specific_topic_tokens(query)
        source_tokens = set(_tokens(source_text))
        if not topic_tokens.intersection(source_tokens):
            return False
    # At least one intent that the question asks about must be evidenced by the source.
    for query_pattern, source_pattern in _CLINICAL_INTENT_GROUPS:
        if re.search(query_pattern, query, re.IGNORECASE) and re.search(source_pattern, source_text or "", re.IGNORECASE):
            return True
    return False


def _is_weather_stem(token: str) -> bool:
    return any(token.startswith(_stem(term)) for term in _WEATHER_WORDS)


def _is_generic_query_token(token: str) -> bool:
    if not token or token in _STOP_WORDS:
        return True
    return (
        token in _GENERIC_QUERY_STEMS
        or any(token.startswith(stem) for stem in _GENERIC_QUERY_STEMS)
        or _is_generic_topic_token(token)
    )


def classify_source_relevance(
    query: str,
    *,
    title: str = "",
    path: str = "",
    section: str = "",
    content: str = "",
    url: str = "",
    source_type: str = "unknown",
) -> RelevanceAssessment:
    """Score the topical fit of one source to a question using metadata and body text.

    Labels: relevant / partial / irrelevant. Weather is handled as a dynamic
    intent and requires a city match where the query specifies a city.
    """
    query = (query or "").strip()
    if not query:
        return RelevanceAssessment(0.0, "irrelevant", "empty_query")

    metadata = f"{title} {path.replace('_', ' ')} {section} {url}"
    full_source = f"{metadata} {content}"
    query_tokens = _tokens(query)
    metadata_tokens = set(_tokens(metadata))
    source_tokens = set(_tokens(full_source))

    preparation_problem = preparation_evidence_problem(
        query, title=title, path=path, section=section, content=content
    )
    if preparation_problem:
        return RelevanceAssessment(
            0.03, "irrelevant", preparation_problem,
            tuple(sorted(set(_tokens(query)) & set(_tokens(f"{title} {section} {content}")))),
        )

    if is_weather_query(query):
        source_has_weather = bool(_WEATHER_RE.search(full_source))
        if not source_has_weather:
            return RelevanceAssessment(0.0, "irrelevant", "weather_intent_missing_from_source")

        query_text = " ".join(_TOKEN_RE.findall(query.lower().replace("ё", "е")))
        source_text = " ".join(_TOKEN_RE.findall(full_source.lower().replace("ё", "е")))
        place_tokens = {
            token for token in query_tokens
            if len(token) >= 5 and not _is_weather_stem(token) and token not in _STOP_WORDS
            and token not in _GENERIC_QUERY_STEMS
        }
        place_hits = sorted(place_tokens.intersection(source_tokens))
        alias_hits: list[str] = []
        for city, aliases in _WEATHER_PLACE_ALIASES.items():
            if city in query_text or any(alias in query_text for alias in aliases):
                matched_alias = next((alias for alias in aliases if alias in source_text), None)
                if matched_alias:
                    alias_hits.append(matched_alias)
        if place_tokens and not place_hits and not alias_hits:
            return RelevanceAssessment(0.08, "irrelevant", "weather_location_mismatch")

        weather_hits = sorted(
            token for token in source_tokens
            if any(token.startswith(_stem(word)) or _stem(word).startswith(token) for word in _WEATHER_WORDS)
        )
        location_confirmed = bool(place_hits or alias_hits)
        score = 0.82 if location_confirmed else 0.48
        if content and len(content.strip()) >= 40:
            score = min(1.0, score + 0.12)
        return RelevanceAssessment(
            score,
            "relevant" if location_confirmed else "partial",
            "weather_and_location_match" if location_confirmed else "weather_match_location_unconfirmed",
            tuple(sorted(set(place_hits + alias_hits + weather_hits))),
        )

    # Scheduling/consultation questions need the section with appointment
    # assignment, not a generic description of what the specialty treats. The
    # Wiki stores these assignments under headings such as "Распределение записи"
    # and "Консультативные приемы", often with the specialty only in the article path.
    requested_specialty = _requested_specialty(query)
    specialist_intent = bool(re.search(
        r"врач\w*|специалист\w*|консультац\w*|запис\w*|при[её]м\w*|обрат\w*|куда\s+запис",
        query,
        re.IGNORECASE,
    ))
    appointment_evidence = bool(re.search(
        r"распределение\s+запис|консультативн\w*\s+при[её]м|список\s+врач|расписани\w*\s+при[её]м|запис\w*\s+к",
        full_source,
        re.IGNORECASE,
    ))
    if requested_specialty and specialist_intent and appointment_evidence:
        specialty_pattern = _SPECIALTY_PATTERNS[requested_specialty]
        if re.search(specialty_pattern, full_source, re.IGNORECASE):
            return RelevanceAssessment(
                0.92,
                "relevant",
                "specialty_appointment_assignment_match",
                (requested_specialty, "appointment_assignment"),
            )

    # A patient asking about parking at a particular branch should see the
    # general patient rules above taxi-only or special-program rules. Keeping this
    # intent-aware classification here prevents a generic parking title from making
    # the wrong subsection look equally useful.
    asks_parking = bool(re.search(r"парков\w*|паркинг|парковат\w*|допуск на территор", query, re.IGNORECASE))
    target_branch = _requested_branch(query)
    section_text = str(section or "").casefold().replace("ё", "е")
    source_text = full_source.casefold().replace("ё", "е")
    if asks_parking and target_branch:
        branch_pattern = _BRANCH_PATTERNS[target_branch]
        branch_matches = bool(re.search(branch_pattern, f"{section_text} {source_text}"))
        if branch_matches:
            patient_rules = bool(re.search(r"для пациент\w* клиник", section_text))
            taxi_only = bool(re.search(
                r"такси|автовладельц\w*|не являющ\w*ся пациент\w*|посадк\w*[/ ]+высадк",
                f"{section_text} {content}".casefold(),
            ))
            has_parking_conditions = bool(re.search(
                r"бесплатн\w*|рубл\w*|\b\d+\s*(?:час|ч\b)|зон\w*\s*[abcа-я]|паркомат|оплат\w*|платн\w*",
                content,
                re.IGNORECASE,
            ))
            if patient_rules and has_parking_conditions:
                return RelevanceAssessment(
                    0.96, "relevant", "requested_branch_general_patient_parking_rules",
                    ("parking", target_branch, "general_patient_rules"),
                )
            if taxi_only and not re.search(r"такси|посадк|высадк|автовладельц", query, re.IGNORECASE):
                return RelevanceAssessment(
                    0.24, "partial", "parking_wrong_subtopic_taxi_only",
                    ("parking", target_branch, "taxi_only"),
                )

    # Broad concept vocabulary supplements lexical overlap: queries such as
    # "где оставить машину" and passages titled "допуск на территорию" can
    # concern the same operational concept without sharing exact keywords.
    # Generic clinical concepts ("diagnosis", "treatment", etc.) are not enough
    # on their own to establish that a passage is about the specific condition asked.
    normalized_query = query.casefold().replace("ё", "е")
    normalized_source = full_source.casefold().replace("ё", "е")

    clinical_concepts = {
        "symptoms",
        "diagnosis",
        "treatment",
        "medication",
        "contraindications",
        "prevention",
        "referral",
        "results",
    }
    context_only_tokens = {
        "взрослый", "взрослых", "взросл", "ребенок", "ребенк", "ребенков",
        "пациент", "пациентов", "пациентам", "adult", "adults", "patient", "patients",
    }
    specific_query_tokens = {
        token
        for token in query_tokens
        if len(token) >= 4
        and not _is_generic_query_token(token)
        and not any(token.startswith(prefix) for prefix in context_only_tokens)
    }
    has_specific_topic_overlap = bool(specific_query_tokens.intersection(source_tokens))

    concept_hits = [
        concept for concept, pattern in _CONCEPT_PATTERNS.items()
        if re.search(pattern, normalized_query, re.IGNORECASE)
        and re.search(pattern, normalized_source, re.IGNORECASE)
    ]
    if concept_hits:
        matched_body_concepts = [
            concept for concept in concept_hits
            if re.search(_CONCEPT_PATTERNS[concept], f"{section} {content}", re.IGNORECASE)
        ]
        has_clinical_concept = bool(set(matched_body_concepts).intersection(clinical_concepts))
        if matched_body_concepts and (
            not has_clinical_concept or has_specific_topic_overlap
        ):
            return RelevanceAssessment(
                0.78, "relevant", "domain_concept_match",
                tuple(sorted(set(matched_body_concepts))),
            )

    key_tokens = [
        token for token in query_tokens
        if len(token) >= 3 and not _is_generic_query_token(token)
    ]
    # Preserve exact short phrases such as "общая информация", which can be a
    # page section name even though both words are too generic to stand alone.
    query_phrase = " ".join(_TOKEN_RE.findall(query.lower()))
    normalized_metadata = " ".join(_TOKEN_RE.findall(metadata.lower()))
    normalized_source = " ".join(_TOKEN_RE.findall(full_source.lower()))
    phrase_hits: list[str] = []
    phrase_tokens = [
        " ".join(_TOKEN_RE.findall(phrase.lower()))
        for phrase in (
            "общая информация", "допуск на территорию", "парковка", "подготовка к гастроскопии",
            "режим работы", "контактная информация", "как добраться", "стоимость услуги",
            "запись на прием", "запись на прием к врачу", "побочные эффекты",
            "противопоказания", "показания к применению", "результаты анализов",
            "парковка для пациентов", "торговый центр", "жк сосновый квартал",
            "подготовка к гастроскопии", "общий анализ крови", "подготовка к кт",
            "подготовка к мрт", "подготовка к колоноскопии", "сдача крови натощак",
        )
    ]
    for phrase in phrase_tokens:
        if phrase in query_phrase and phrase in normalized_source:
            phrase_hits.append(phrase)

    if not key_tokens and not phrase_hits:
        return RelevanceAssessment(0.05, "partial", "no_specific_query_terms")

    unique_key_tokens = list(dict.fromkeys(key_tokens))
    metadata_hits = set(unique_key_tokens).intersection(metadata_tokens)
    body_hits = set(unique_key_tokens).intersection(source_tokens)
    # Metadata matches are worth more than body-only mentions, while RAG's own
    # RRF score will continue to provide the primary ranking signal downstream.
    weighted_coverage = (
        2.0 * len(metadata_hits) + len(body_hits - metadata_hits)
    ) / (2.0 * max(1, len(unique_key_tokens)))
    score = min(1.0, weighted_coverage)
    if phrase_hits:
        score = max(score, 0.72)
    matched = tuple(sorted(metadata_hits | body_hits | set(phrase_hits)))
    if score >= 0.52:
        return RelevanceAssessment(score, "relevant", "query_terms_match_source", matched)
    if score >= 0.20:
        return RelevanceAssessment(score, "partial", "partial_query_term_overlap", matched)
    return RelevanceAssessment(score, "irrelevant", "insufficient_query_term_overlap", matched)


def answerability_score(
    query: str,
    *,
    title: str = "",
    path: str = "",
    section: str = "",
    content: str = "",
    source_score: float = 0.0,
    content_score: float = 0.0,
) -> tuple[float, str]:
    """Estimate whether a specific passage answers the requested sub-question.

    This is a ranking feature, not a gate. It distinguishes related but non-answering
    chunks (for example, lost-ticket instructions) from parking-fee rules.
    """
    query_norm = (query or "").casefold().replace("ё", "е")
    passage_norm = f"{section} {content}".casefold().replace("ё", "е")
    source_norm = f"{title} {path}".casefold().replace("ё", "е")
    base = 0.45 * float(source_score) + 0.55 * float(content_score)
    reason = "topical_overlap"

    requested_specialty = _requested_specialty(query_norm)
    # Operation-only sections should not outrank injury triage or general booking
    # instructions merely because the parent article is a traumatologist page.
    is_operation_consultation = bool(re.search(
        r"консультац\w*\s+(?:по\s+)?операц\w*|оперативн\w*\s+лечен\w*|подготовк\w*\s+к\s+операц\w*",
        section.casefold().replace("ё", "е"),
    ))
    asks_about_operation = bool(re.search(
        r"операц\w*|оперативн\w*\s+лечен\w*|хирургическ\w*\s+вмешательств\w*",
        query_norm,
    ))
    if is_operation_consultation and not asks_about_operation:
        base -= 0.65
        reason = "operation_consultation_not_requested"

    specialist_intent = bool(re.search(
        r"врач\w*|специалист\w*|консультац\w*|запис\w*|при[её]м\w*|обрат\w*|куда\s+запис",
        query_norm,
    ))
    appointment_evidence = bool(re.search(
        r"распределение\s+запис|консультативн\w*\s+при[её]м|список\s+врач|расписани\w*\s+при[её]м|запис\w*\s+к",
        passage_norm,
    ))
    if requested_specialty and specialist_intent and appointment_evidence:
        if re.search(_SPECIALTY_PATTERNS[requested_specialty], source_norm, re.IGNORECASE):
            # This chunk answers "which doctors can I book?" directly, unlike a
            # disease overview or a list of indications for seeing the specialist.
            base = max(base, 0.94)
            reason = "specialty_appointment_assignment"

    asks_parking_or_access = bool(re.search(
        r"парков\w*|паркинг|парковат\w*|допуск|доступ на территор", query_norm
    )) or bool(re.search(r"парков\w*|паркинг", source_norm) and re.search(r"допуск|территор", query_norm))
    if not asks_parking_or_access:
        return round(max(0.0, min(1.0, base)), 3), reason

    asks_lost_ticket = bool(re.search(
        r"потер\w*|утер\w*|пропал\w*|потерян\w*|lost ticket|lost parking", query_norm
    ))
    is_lost_ticket_passage = bool(re.search(
        r'утерянн\w*\s+талон|потерянн\w*\s+талон|печать утерянного талона|\"потерял\w* парковочн\w* талон',
        passage_norm,
    ))
    parking_rule_evidence = bool(re.search(
        r"бесплатн\w*|рубл\w*|\b\d+\s*(?:час|ч\b)|\b\d+\s*руб|зон\w*\s*[abcа-я]|"
        r"паркомат|оплат\w*|платн\w*|въезд|выезд|аннулир\w* талон|покинуть парковк",
        passage_norm,
    ))
    if is_lost_ticket_passage and not asks_lost_ticket:
        base -= 0.55
        reason = "related_topic_but_wrong_subtopic_lost_ticket"
    elif parking_rule_evidence:
        base += 0.22
        reason = "parking_rules_or_conditions_in_passage"

    body_without_headings = re.sub(r"(?m)^\s*#{1,6}\s+.*$", " ", content or "")
    body_without_headings = re.sub(r"(?m)^\s*[-*]+\s*$", " ", body_without_headings).strip()
    if len(body_without_headings) < 35 and not parking_rule_evidence and not is_lost_ticket_passage:
        base -= 0.35
        reason = "passage_has_no_answer_bearing_body_text"

    target_branch = _requested_branch(query_norm)
    section_only = section.casefold().replace("ё", "е")
    known_branch_hits = [
        name for name, pattern in _BRANCH_PATTERNS.items()
        if re.search(pattern, section_only)
    ]
    if target_branch:
        target_pattern = _BRANCH_PATTERNS[target_branch]
        if re.search(target_pattern, section_only):
            base += 0.30
            reason = "requested_branch_matches_passage"
        elif known_branch_hits:
            base -= 0.45
            reason = "passage_is_for_another_branch"
        else:
            base -= 0.10

    asks_taxi = bool(re.search(r"такси|автовладельц\w*|посадк\w*|высадк\w*", query_norm))
    is_taxi_specific = bool(re.search(
        r"такси|автовладельц\w*|не являющ\w*ся пациент\w*",
        f"{section} {content}".casefold(),
    ))
    if is_taxi_specific and not asks_taxi:
        base -= 0.45
        reason = "wrong_subtopic_taxi_only"

    asks_inpatient = bool(re.search(r"стационар\w*|ночн\w* парковк\w*|ночев\w*", query_norm))
    is_inpatient_specific = bool(re.search(r"стационар\w*|ночн\w* парковк\w*", section.casefold()))
    if is_inpatient_specific and not asks_inpatient:
        base -= 0.50
        reason = "special_inpatient_conditions_not_requested"

    special_sections = (
        (r"травмпункт\w*|травм\w*", r"травмпункт\w*|травм\w*", "trauma_patient_conditions_not_requested"),
        (r"роддом\w*|родильн\w*", r"роддом\w*|родильн\w*|рождени\w* ребен\w*", "maternity_conditions_not_requested"),
        (r"беремен\w*|наблюдени\w* ребен\w*", r"беремен\w*|наблюдени\w* ребен\w*", "program_specific_conditions_not_requested"),
    )
    for section_pattern, query_pattern, subtopic_reason in special_sections:
        if re.search(section_pattern, section.casefold()) and not re.search(query_pattern, query_norm):
            base -= 0.50
            reason = subtopic_reason

    section_norm = section.casefold().replace("ё", "е")
    general_patient_section = bool(re.search(r"для пациент\w* клиник", section_norm))
    if general_patient_section and not asks_taxi:
        base += 0.08
        reason = "general_patient_parking_conditions"

    if re.search(r"пациент\w*", query_norm) and re.search(r"пациент\w*", passage_norm):
        base += 0.04

    return round(max(0.0, min(1.0, base)), 3), reason
