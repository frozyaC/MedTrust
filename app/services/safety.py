import re
from dataclasses import dataclass
from urllib.parse import urlparse


# MVP scope guard. The project should accept medical questions, adjacent clinic
# workflows, and questions about the indexed Wiki.js content. The vocabulary is
# intentionally broad, while the explicit out-of-scope list blocks common
# unrelated requests.
MEDICAL_TERMS = {
    "врач", "врача", "врачу", "врачи", "доктор", "доктора", "обратиться", "пациент", "пациента", "пациенту",
    "боль", "боли", "больной", "болезнь", "заболевание", "симптом", "симптомы",
    "диагноз", "диагностика", "лечение", "лечить", "терапия", "операция",
    "хирург", "хирургия", "травма", "травмы", "травматолог", "травмпункт",
    "ортопед", "ревматолог", "сустав", "суставы", "артрит", "артроз",
    "перелом", "вывих", "ушиб", "связка", "сухожилие", "рана", "инфекция",
    "температура", "давление", "анализ", "анализы", "кровь", "моча", "узи",
    "мрт", "кт", "рентген", "экг", "препарат", "препараты", "лекарство",
    "лекарства", "доза", "дозировка", "противопоказание", "противопоказания",
    "анамнез", "осмотр", "консультация", "прием", "приём", "запись", "записать",
    "клиника", "медицинский", "медицина", "дипансер", "специалист", "специалиста",
    "анестезия", "вакцина", "вакцинация", "беременность", "аллергия", "аллергия",
    "реабилитация", "перевязка", "гипс", "пульс", "сатурация", "диета",
}

# Common Russian medical stems are matched by prefix so inflected forms such as
# "диагностике", "диагностический" and "мигрени" are not rejected.
MEDICAL_STEMS = {
    "медицин", "медиц", "пациент", "врач", "доктор", "болезн", "заболев",
    "симптом", "диагност", "лечени", "лечит", "терап", "операц", "хирург",
    "травм", "ортопед", "ревматолог", "сустав", "артрит", "артроз", "перелом",
    "вывих", "ушиб", "связк", "сухожил", "инфекц", "температур", "давлен",
    "анализ", "кров", "моч", "узи", "мрт", "рентген", "препарат", "лекарств",
    "дозиров", "противопоказ", "анамнез", "осмотр", "консультац", "прием", "приём",
    "запис", "клиник", "диспанс", "специалист", "анестез", "вакцин", "беремен",
    "аллерг", "реабилит", "перевяз", "гипс", "пульс", "сатурац", "диет",
    "рекомендац", "мигрен", "синдром", "скрининг", "онколог", "гематолог",
}

OUT_OF_SCOPE_TERMS = {
    "политика", "президент", "выборы", "партия", "политик", "ставка", "акции",
    "биткоин", "криптовалюта", "крипта", "программирование", "python", "javascript",
    "код", "docker", "git", "погода", "ресторан", "туризм", "отель", "фильм",
    "музыка", "спорт", "футбол", "баскетбол", "игра", "игры",
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[а-яёa-z0-9]+", text.lower()))


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str


class QueryScopeValidator:
    def validate(self, query: str) -> ScopeDecision:
        tokens = _tokens(query)
        if not tokens:
            return ScopeDecision(False, "Пустой запрос")

        blocked = tokens & OUT_OF_SCOPE_TERMS
        if blocked:
            return ScopeDecision(False, "Запрос не относится к медицинской тематике MedTrust")

        if tokens & MEDICAL_TERMS:
            return ScopeDecision(True, "medical vocabulary")

        if any(any(token.startswith(stem) for stem in MEDICAL_STEMS) for token in tokens):
            return ScopeDecision(True, "medical vocabulary (inflected form)")

        # Path-aware retrieval will still allow a question about an indexed Wiki
        # topic even if it contains no canonical medical term.
        lowered = query.lower()
        if any(marker in lowered for marker in ("wiki", "статья", "раздел", "регистратур", "записи")):
            return ScopeDecision(True, "Wiki.js / clinic workflow context")

        return ScopeDecision(False, "Недостаточно признаков медицинской тематики")


DEFAULT_SAFE_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "who.int",
    "cdc.gov",
    "fda.gov",
    "ema.europa.eu",
    "nice.org.uk",
    "nhs.uk",
    "medlineplus.gov",
    "mayoclinic.org",
    "msdmanuals.com",
    "minzdrav.gov.ru",
    "cr.minzdrav.gov.ru",
}


def is_safe_domain(url: str, allowed_domains: set[str]) -> bool:
    try:
        hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if not hostname or urlparse(url).scheme not in {"http", "https"}:
        return False
    return any(hostname == domain or hostname.endswith("." + domain) for domain in allowed_domains)
