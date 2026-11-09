"""Prompt-injection boundary helpers for retrieved and conversational content.

Detection is advisory only: the module never deletes or rewrites source text.
All caller-controlled/retrieved text is JSON-serialized before being embedded in
an LLM prompt so that delimiters and newlines cannot escape the data container.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Iterable

_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_WHITESPACE_RE = re.compile(r"\s+")

# These patterns intentionally target meta-instructions about the model/prompt,
# secret disclosure, or control-flow changes. Ordinary medical imperatives such as
# "не принимать пищу перед процедурой" must not be flagged.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override_previous_instructions_en",
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?"
            r"(?:the\s+)?(?:previous|prior|above|earlier|system|developer)\s+"
            r"(?:instructions?|rules?|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_hidden_prompt_or_secrets_en",
        re.compile(
            r"\b(?:reveal|print|show|dump|expose|leak|repeat)\b.{0,100}\b"
            r"(?:system\s+prompt|developer\s+(?:message|prompt)|hidden\s+prompt|"
            r"api\s+keys?|access\s+tokens?|credentials?|passwords?|environment\s+variables?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltrate_data_en",
        re.compile(
            r"\b(?:send|exfiltrate|forward|upload|transmit)\b.{0,100}\b"
            r"(?:secrets?|credentials?|api\s+keys?|tokens?|conversation\s+history|"
            r"environment\s+variables?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_or_policy_override_en",
        re.compile(
            r"\b(?:you\s+are\s+now|act\s+as|switch\s+to)\s+(?:the\s+)?"
            r"(?:system|developer|administrator|admin)\b|"
            r"\bnew\s+system\s+prompt\b",
            re.IGNORECASE,
        ),
    ),
    (
        "override_previous_instructions_ru",
        re.compile(
            r"\b(?:игнорируй|забудь|отмени|отбрось|не\s+учитывай)\s+(?:все\s+)?"
            r"(?:предыдущие|прежние|вышеуказанные|системные|разработчика)\s+"
            r"(?:инструкции|правила|указания|промпты?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_hidden_prompt_or_secrets_ru",
        re.compile(
            r"\b(?:покажи|раскрой|выведи|напечатай|повтори|слей)\b.{0,100}\b"
            r"(?:системн\w*\s+(?:промпт|инструкц|сообщен)|"
            r"скрыт\w*\s+(?:инструкц|сообщен)|api[\s_-]*ключ\w*|"
            r"токен\w*|парол\w*|секрет\w*|переменн\w*\s+окружени\w*)",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltrate_data_ru",
        re.compile(
            r"\b(?:отправь|передай|загрузи|перешли|опубликуй)\b.{0,100}\b"
            r"(?:секрет\w*|ключ\w*|токен\w*|парол\w*|переписк\w*|"
            r"истори\w*\s+(?:диалога|сообщений)|переменн\w*\s+окружени\w*)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_or_policy_override_ru",
        re.compile(
            r"\b(?:ты\s+теперь|действуй\s+как|переключись\s+в\s+режим)\s+"
            r"(?:систем\w*|разработчик\w*|администратор\w*)\b|"
            r"\bновая\s+системная\s+инструкция\b",
            re.IGNORECASE,
        ),
    ),
    (
        "structured_prompt_boundary_marker",
        re.compile(
            r"<\|im_start\|>\s*system|<\|system\|>|<<\s*sys\s*>>|"
            r"\[\s*system\s*\]|###\s*(?:system|developer)\b",
            re.IGNORECASE,
        ),
    ),
)

_SOURCE_ID_RE = re.compile(
    r"\[(?:Wiki-Источник|Web-Источник)\s+(W\d+|WEB\d+)\]|"
    r"^\s*\[(W\d+|WEB\d+)\]",
    re.IGNORECASE | re.MULTILINE,
)


def _normalise_for_detection(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = _ZERO_WIDTH_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).casefold()


def detect_prompt_injection(value: str) -> list[str]:
    """Return stable signal IDs for instruction-like text; do not redact content."""
    normalized = _normalise_for_detection(value)
    return [signal for signal, pattern in _INJECTION_PATTERNS if pattern.search(normalized)]


def serialize_untrusted_context(value: str, context_type: str) -> str:
    """Serialize history/summary/previous answers as data, not prompt instructions."""
    content = str(value or "")
    payload = {
        "trust_boundary": "UNTRUSTED_CONTEXT_DATA",
        "context_type": str(context_type),
        "instruction_like_text_detected": bool(detect_prompt_injection(content)),
        "content": content,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def serialize_untrusted_sources(blocks: Iterable[str]) -> str:
    """Serialize source blocks while preserving their complete original text."""
    records = []
    for block in blocks:
        content = str(block or "")
        match = _SOURCE_ID_RE.search(content)
        source_id = next((group for group in match.groups() if group), None) if match else None
        records.append({
            "source_id": source_id,
            "trust_boundary": "UNTRUSTED_RETRIEVED_EVIDENCE",
            "instruction_like_text_detected": bool(detect_prompt_injection(content)),
            "content": content,
        })
    return json.dumps(
        {"format": "medtrust_untrusted_sources_v1", "records": records},
        ensure_ascii=False,
        separators=(",", ":"),
    )
