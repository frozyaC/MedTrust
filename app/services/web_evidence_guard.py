"""Intent-specific evidence guards for price and contraindication questions.

This module intentionally uses only the Python standard library so its decision rules
can be unit-tested without booting the full MedTrust application.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_SPACE_RE = re.compile(r"\s+")

_PRICE_INTENT = re.compile(
    r"цен\w*|стоимост\w*|сколько\s+стоит|поч[её]м|тариф\w*|price|cost|pricing",
    re.IGNORECASE,
)
_CONTRAINDICATION_INTENT = re.compile(
    r"противопоказ\w*|кому\s+нельзя|когда\s+нельзя|что\s+нельзя|"
    r"contraindicat\w*|who\s+should\s+not|safety\s+concern",
    re.IGNORECASE,
)
_FREE_PRICE = re.compile(r"бесплатн\w*|без\s+оплат\w*|no\s+charge|free\s+of\s+charge", re.I)
_MONEY_AMOUNT = re.compile(
    r"(?:\d{1,3}(?:[\s\u00a0\u202f]\d{3})+|\d{1,9})(?:[,.]\d{1,2})?\s*"
    r"(?:₽|руб(?:\.|л(?:ь|я|ей)?)?|₸|тенге|тг\.?|€|евро|\$|usd|eur|kzt|"
    r"сом(?:а|ов)?|сомони|грн|₴)"
    r"|(?:₽|₸|€|\$|₴)\s*\d[\d\s\u00a0\u202f]*(?:[,.]\d{1,2})?",
    re.IGNORECASE,
)

_PROCEDURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("gastroscopy", re.compile(r"гастроскоп\w*|фгдс|эзофагогастродуоденоскоп\w*|gastroscop\w*|upper\s+endoscop\w*|\begd\b", re.I)),
    ("mri", re.compile(r"\bмрт\b|магнитно.?резонанс\w*|\bmri\b|magnetic\s+resonance", re.I)),
    ("colonoscopy", re.compile(r"колоноскоп\w*|colonoscopy|colonoscope", re.I)),
    ("ct", re.compile(r"\bкт\b|компьютерн\w*\s+томограф\w*|\bct\s+scan\b|computed\s+tomography", re.I)),
    ("ultrasound", re.compile(r"\bузи\b|ультразвуков\w*|ultrasound|sonograph\w*", re.I)),
    ("blood_test", re.compile(r"анализ\w*\s+кров\w*|общ\w*\s+анализ\w*\s+кров\w*|blood\s+test|\bcbc\b|complete\s+blood\s+count", re.I)),
)

_CONTRAST = re.compile(r"контраст\w*|гадолин\w*|gadolinium|\bgad\b|contrast\w*", re.I)
_RISK_EVIDENCE = re.compile(
    r"противопоказ\w*|contraindicat\w*|безопасност\w*|safety|"
    r"аллерг\w*|allerg\w*|почек|почечн\w*|kidney|renal|"
    r"беремен\w*|pregnan\w*|имплант\w*|implant\w*|"
    r"побочн\w*\s+реакц\w*|adverse\s+reaction\w*|"
    r"нефроген\w*|nephrogenic|фиброз\w*|fibrosis|гадолин\w*|gadolinium",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").casefold().replace("ё", "е")).strip()


def is_price_query(query: str) -> bool:
    return bool(_PRICE_INTENT.search(_normalize(query)))


def is_contraindication_query(query: str) -> bool:
    return bool(_CONTRAINDICATION_INTENT.search(_normalize(query)))


def has_explicit_price(text: str) -> bool:
    normalized = _normalize(text)
    return bool(_MONEY_AMOUNT.search(normalized) or _FREE_PRICE.search(normalized))


def _procedure_for_query(query: str) -> tuple[str, re.Pattern[str]] | None:
    for name, pattern in _PROCEDURES:
        if pattern.search(query or ""):
            return name, pattern
    return None


def _price_spans(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in _MONEY_AMOUNT.finditer(text)]
    spans.extend((m.start(), m.end()) for m in _FREE_PRICE.finditer(text))
    return spans


def _price_is_linked_to_service(
    procedure_name: str, procedure_pattern: re.Pattern[str], source_fields: tuple[str, ...]
) -> bool:
    """Require a price/free statement near the requested procedure in one source passage."""
    nonempty = [_normalize(value) for value in source_fields if value]
    candidates = list(nonempty)
    # Search snippets often omit the procedure name shown in the result title. Pair
    # title with the passage, but still require local proximity and no intervening
    # mention of a different known procedure.
    for index, left in enumerate(nonempty):
        for right in nonempty[index + 1:]:
            candidates.append(f"{left} {right}")
    for candidate in candidates:
        procedure_matches = list(procedure_pattern.finditer(candidate))
        if not procedure_matches:
            continue
        price_spans = _price_spans(candidate)
        for procedure_match in procedure_matches:
            for price_start, price_end in price_spans:
                if min(abs(price_start - procedure_match.end()), abs(procedure_match.start() - price_end)) > 250:
                    continue
                left, right = sorted((procedure_match.end(), price_start))
                if price_start < procedure_match.start():
                    left, right = price_end, procedure_match.start()
                between = candidate[left:right]
                other_procedure_found = any(
                    name != procedure_name and pattern.search(between)
                    for name, pattern in _PROCEDURES
                )
                if not other_procedure_found:
                    return True
    return False


def evidence_rejection_reason(
    query: str, *, title: str = "", url: str = "", snippet: str = "", content: str = ""
) -> str | None:
    """Return a reason to reject a candidate that does not answer a price/safety query.

    A ``None`` result means this guard has no reason to reject the candidate. This is
    deliberately stricter for these two intents than generic topical relevance.
    """
    normalized_query = _normalize(query)
    # Keep the URL path as a weak document hint, but exclude query parameters that may
    # simply echo the user's search string and falsely make an unrelated page look relevant.
    try:
        url_path = urlsplit(url or "").path
    except ValueError:
        url_path = ""
    source_text = _normalize(" ".join((title, url_path, snippet, content)))

    if is_price_query(normalized_query):
        procedure = _procedure_for_query(normalized_query)
        if procedure and not procedure[1].search(source_text):
            return "price_procedure_mismatch"
        if not has_explicit_price(source_text):
            return "price_requires_explicit_amount"
        if procedure and not _price_is_linked_to_service(
            procedure[0], procedure[1], (title, snippet, content, url_path)
        ):
            return "price_amount_not_linked_to_service"

    if is_contraindication_query(normalized_query):
        procedure = _procedure_for_query(normalized_query)
        if procedure and not procedure[1].search(source_text):
            return "contraindication_procedure_mismatch"
        asks_contrast = bool(_CONTRAST.search(normalized_query))
        if asks_contrast and not _CONTRAST.search(source_text):
            return "contraindication_contrast_mismatch"
        if not _RISK_EVIDENCE.search(source_text):
            return "contraindication_evidence_missing"

    return None
