"""LLM-based query rewriting for MedTrust conversation follow-ups.

The contextualizer only normalizes a search query. It never answers the user's
question and does not receive the separately supplied patient profile.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import get_settings
from app.db.database import get_connection
from app.services.gigachat import GigaChatClient

logger = logging.getLogger(__name__)

_ALLOWED_INTENTS = {
    "new_question",
    "follow_up",
    "compound_question",
    "ambiguous",
    "out_of_scope",
}
_CONFIDENCE_THRESHOLD = 0.60
_MAX_QUESTION_CHARS = 1200
_MAX_RESOLVED_QUERY_CHARS = 1200
_MAX_ENTITY_VALUE_CHARS = 200

# Deliberately small deterministic aliases: these protect the most common registrar
# follow-ups when the LLM is unavailable or returns an underspecified query.
_SERVICE_PATTERNS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "gastroscopy",
        "гастроскопия",
        "гастроскопии",
        (r"гастроскоп\w*", r"фгдс", r"эзофагогастродуоденоскоп\w*", r"gastroscop\w*"),
    ),
    (
        "cbc",
        "общий анализ крови (ОАК)",
        "общего анализа крови (ОАК)",
        (r"(?<![а-яё])оак(?![а-яё])", r"общ\w*\s+анализ\w*\s+кров\w*", r"complete blood count", r"\bcbc\b"),
    ),
    (
        "biochemistry",
        "биохимический анализ крови",
        "биохимического анализа крови",
        (r"биохим\w*(?:\s+анализ\w*)?(?:\s+кров\w*)?", r"blood chemistry", r"biochemical blood test"),
    ),
    (
        "colonoscopy",
        "колоноскопия",
        "колоноскопии",
        (r"колоноскоп\w*", r"colonoscop\w*"),
    ),
    (
        "mri",
        "МРТ",
        "МРТ",
        (r"(?<![а-яё])мрт(?![а-яё])", r"магнитно-резонансн\w*", r"magnetic resonance"),
    ),
    (
        "ct",
        "КТ",
        "КТ",
        (r"(?<![а-яё])кт(?![а-яё])", r"компьютерн\w*\s+томограф\w*", r"computed tomography"),
    ),
    (
        "ultrasound",
        "УЗИ",
        "УЗИ",
        (r"(?<![а-яё])узи(?![а-яё])", r"ультразвуков\w*\s+исследован\w*", r"ultrasound"),
    ),
)

_FACET_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cabinet", (r"кабинет\w*", r"номер\s+кабинет\w*", r"room\s*\w*")),
    ("phone", (r"телефон\w*", r"контакт\w*", r"номер\s+телефон\w*", r"phone\w*")),
    ("price", (r"стоимост\w*", r"цен\w*", r"сколько(?:\s+стоит)?")),
    ("preparation", (r"подготов\w*", r"как подготовиться")),
    ("timing", (r"срок\w*", r"когда", r"длительност\w*")),
    ("location", (r"адрес\w*", r"располож\w*", r"где")),
    ("composition", (r"состав\w*", r"что входит")),
    ("contraindications", (r"противопоказан\w*", r"ограничен\w*")),
)

_OBVIOUS_TYPO_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("подготвока", "подготовка"),
    ("подготвке", "подготовке"),
    ("гатроскопия", "гастроскопия"),
    ("гатроскопии", "гастроскопии"),
    ("гатроскопией", "гастроскопией"),
    ("гатроскопию", "гастроскопию"),
    ("гастроскопие", "гастроскопии"),
    ("миакарда", "миокарда"),
)

_CONTEXTUALIZER_SYSTEM_PROMPT = """
Ты — LLM Contextualizer приложения MedTrust. Твоя задача — только преобразовать текущий
вопрос регистратора в самостоятельный запрос для поиска. Не отвечай на вопрос, не давай
медицинских рекомендаций и не добавляй фактов, которых нет в текущем вопросе или истории.

Определи intent строго из списка: new_question, follow_up, compound_question, ambiguous,
out_of_scope. Восстанови пропущенный объект по истории, исправь только очевидные опечатки,
выдели сущности и атрибут запроса. resolved_query должен быть самостоятельным кратким
поисковым запросом на русском языке — не включай туда инструкцию о предыдущем вопросе.

Если текущий короткий вопрос можно отнести к нескольким услугам/темам или объект нельзя
надёжно восстановить, не угадывай: верни intent=ambiguous, resolved_query=null,
clarification_required=true и короткий clarification_question на русском языке.
Примеры коротких уточнений: «стоимость», «подготовка», «срок», «адрес», «а сколько стоит?».
При наличии одного однозначного объекта в истории восстанавливай самостоятельный запрос.
Не трактуй само наличие истории как доказательство, что новая тема относится к предыдущей.
Не используй отдельные данные профиля пациента: они обрабатываются RAG независимо.

Верни только один JSON-объект без Markdown и без текста до/после него со следующими полями:
{
  "intent": "follow_up",
  "resolved_query": "самостоятельный поисковый запрос или null",
  "entities": {"service": "название услуги/анализа/процедуры, если определено"},
  "corrections": [{"original": "исходная опечатка", "corrected": "исправление", "source": "llm"}],
  "confidence": 0.0,
  "clarification_required": false,
  "clarification_question": null
}
confidence — число от 0 до 1. При intent=ambiguous или уверенности ниже 0.60 для уточняющего
вопроса обязательно запроси уточнение. Не выдумывай услугу, врача, процедуру или факт.
""".strip()

_STORAGE_LOCK = threading.Lock()
_STORAGE_READY = False


@dataclass(slots=True)
class ContextualizationResult:
    """Validated output of the contextualization stage."""

    intent: str
    resolved_query: str | None
    entities: dict[str, Any]
    corrections: list[dict[str, Any]]
    confidence: float
    clarification_required: bool
    clarification_question: str | None
    depends_on_message_id: str | None = None
    llm_attempted: bool = False
    status: str = "ok"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMContextualizer:
    """Resolve follow-up questions using a bounded conversation history."""

    _FRAGMENT_RE = re.compile(
        r"^(?:а\s+)?(?:телефон\w*|контакт\w*|номер(?:\s+телефон\w*)?|"
        r"номер\s+кабинет\w*|кабинет\w*|стоимость|цена|цену|цене|подготовка|подготовке|срок|сроки|"
        r"адрес|расположение|где|когда|состав|противопоказания|ограничения|"
        r"перечень|список|сколько(?:\s+стоит)?|что\s+по\s+цене|и\s+сколько)\s*[?.!,]*$",
        re.IGNORECASE,
    )

    _ATTRIBUTE_PREFIXES = (
        "телефон", "контакт", "номер", "кабинет", "стоимость", "цена", "цену",
        "подготовка", "подготовке", "срок", "сроки", "адрес", "расположение",
        "где", "когда", "состав", "противопоказания", "ограничения", "перечень",
        "список", "сколько",
    )

    _ENTITY_KEYS = (
        "subject", "doctor", "specialist", "service", "analysis", "laboratory_test",
        "procedure", "appointment_type", "clinic", "test",
    )

    def __init__(self, gigachat: GigaChatClient) -> None:
        self.gigachat = gigachat

    @classmethod
    def _ensure_storage(cls) -> None:
        """Create additive query-context storage without touching Wiki tables."""
        global _STORAGE_READY
        if _STORAGE_READY:
            return
        with _STORAGE_LOCK:
            if _STORAGE_READY:
                return
            with get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversation_query_context (
                        query_id UUID PRIMARY KEY,
                        conversation_id UUID NOT NULL
                            REFERENCES conversations(id) ON DELETE CASCADE,
                        raw_question TEXT NOT NULL,
                        resolved_query TEXT,
                        intent TEXT NOT NULL,
                        resolved_entities JSONB NOT NULL DEFAULT '{}'::jsonb,
                        corrections JSONB NOT NULL DEFAULT '[]'::jsonb,
                        confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0
                            CHECK (confidence >= 0.0 AND confidence <= 1.0),
                        clarification_required BOOLEAN NOT NULL DEFAULT FALSE,
                        clarification_question TEXT,
                        depends_on_message_id UUID
                            REFERENCES chat_messages(id) ON DELETE SET NULL,
                        active_topic TEXT,
                        status TEXT NOT NULL DEFAULT 'ok',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS conversation_query_context_recent_idx
                    ON conversation_query_context (conversation_id, created_at DESC)
                    """
                )
                conn.commit()
            _STORAGE_READY = True

    @staticmethod
    def _decode_json(value: Any, default: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return default

    @classmethod
    def _is_fragment(cls, question: str) -> bool:
        cleaned = re.sub(r"\s+", " ", (question or "").strip().casefold().replace("ё", "е"))
        return bool(cleaned and cls._FRAGMENT_RE.fullmatch(cleaned))

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        candidate = (text or "").strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("GigaChat did not return a JSON object")
        parsed = json.loads(candidate[start : end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("Contextualizer JSON root must be an object")
        return parsed

    @classmethod
    def _clean_entities(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        cleaned: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()[:80]
            if not key or raw_value is None:
                continue
            if isinstance(raw_value, str):
                text = raw_value.strip()[:_MAX_ENTITY_VALUE_CHARS]
                if text:
                    cleaned[key] = text
            elif isinstance(raw_value, (int, float, bool)):
                cleaned[key] = raw_value
            elif isinstance(raw_value, list):
                items = [str(item).strip()[:_MAX_ENTITY_VALUE_CHARS] for item in raw_value]
                cleaned[key] = [item for item in items if item][:10]
        return cleaned

    @staticmethod
    def _clean_corrections(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for item in value[:10]:
            if not isinstance(item, dict):
                continue
            original = str(item.get("original") or "").strip()[:120]
            corrected = str(item.get("corrected") or "").strip()[:120]
            if original and corrected:
                result.append(
                    {
                        "original": original,
                        "corrected": corrected,
                        # This MVP does not load a canonical dictionary, so do not
                        # claim a dictionary-based correction was applied.
                        "source": "llm",
                    }
                )
        return result

    @classmethod
    def _topic_from_state(cls, state: dict[str, Any]) -> str | None:
        entities = state.get("entities")
        if isinstance(entities, dict):
            for key in cls._ENTITY_KEYS:
                value = entities.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:_MAX_ENTITY_VALUE_CHARS]
        active_topic = state.get("active_topic")
        if isinstance(active_topic, str) and active_topic.strip():
            return active_topic.strip()[:_MAX_ENTITY_VALUE_CHARS]
        last_resolved = state.get("last_resolved_query")
        if isinstance(last_resolved, str) and last_resolved.strip():
            return last_resolved.strip()[:_MAX_RESOLVED_QUERY_CHARS]
        return None

    @staticmethod
    def _clarification_for(question: str) -> str:
        cleaned = (question or "").casefold().replace("ё", "е")
        if re.search(r"стоимост|цен[ауыые]?|сколько", cleaned):
            return (
                "Уточните, пожалуйста, стоимость какой услуги, анализа или процедуры "
                "вас интересует?"
            )
        if re.search(r"подготов", cleaned):
            return "Уточните, пожалуйста, к какой услуге или процедуре нужна подготовка?"
        if re.search(r"срок|когда", cleaned):
            return "Уточните, пожалуйста, сроки какой услуги или исследования вас интересуют?"
        if re.search(r"кабинет", cleaned):
            return "Уточните, пожалуйста, кабинет какого специалиста или врача нужно найти?"
        if re.search(r"телефон|контакт|номер", cleaned):
            return (
                "Уточните, пожалуйста, телефон или контакты какого специалиста "
                "либо подразделения вас интересуют?"
            )
        if re.search(r"адрес|располож|где", cleaned):
            return "Уточните, пожалуйста, адрес какого филиала или кабинета нужно найти?"
        if re.search(r"состав", cleaned):
            return "Уточните, пожалуйста, состав какой услуги или исследования вас интересует?"
        return "Уточните, пожалуйста, к какой услуге или теме относится ваш вопрос?"

    @classmethod
    def _candidate_services(cls, text: str) -> list[dict[str, str]]:
        """Return distinct recognized medical services found in one context string."""
        value = (text or "").casefold().replace("ё", "е")
        found: list[dict[str, str]] = []
        has_biochemistry = bool(re.search(r"биохим\w*|blood chemistry|biochemical blood test", value))
        for key, nominative, genitive, patterns in _SERVICE_PATTERNS:
            # A generic 'анализ крови' inside a biochemistry phrase should not add OAK.
            if key == "cbc" and has_biochemistry and not re.search(
                r"(?<![а-яё])оак(?![а-яё])|общ\w*\s+анализ\w*\s+кров\w*", value
            ):
                continue
            if any(re.search(pattern, value, re.IGNORECASE) for pattern in patterns):
                found.append({"key": key, "name": nominative, "genitive": genitive})
        return found

    @staticmethod
    def _facet_key(question: str) -> str | None:
        value = (question or "").casefold().replace("ё", "е")
        for facet, patterns in _FACET_PATTERNS:
            if any(re.search(pattern, value) for pattern in patterns):
                return facet
        return None

    @classmethod
    def _pending_subject(cls, state: dict[str, Any]) -> str | None:
        """Recover the object of a pending clarification without trusting a one-word reply."""
        pending_question = str(state.get("pending_question") or "").strip()
        pending_prompt = str(state.get("pending_clarification_question") or "").strip()
        # Prefer the original wording: it preserves the exact inflected form of a proper
        # name (e.g. "Гараевой") rather than a model-normalized nominative form.
        subject_patterns = (
            r"\b(?:кабинет\w*|врач\w*|доктор\w*|специалист\w*|телефон\w*|номер\w*)"
            r"\s+(?:врача\s+)?(?P<subject>[А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+){0,2})",
            r"\bу\s+(?P<subject>[А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+){0,2})",
        )
        for source_text in (pending_question, pending_prompt):
            for pattern in subject_patterns:
                match = re.search(pattern, source_text)
                if match:
                    return match.group("subject").strip()[:_MAX_ENTITY_VALUE_CHARS]

        preferred_keys = (
            "subject", "doctor", "specialist", "physician", "person", "employee",
            "staff_member", "clinic", "department", "service", "procedure",
            "appointment_type", "analysis", "laboratory_test", "test",
        )
        for source_key in ("pending_entities", "entities"):
            entities = state.get(source_key)
            if not isinstance(entities, dict):
                continue
            for key in preferred_keys:
                value = entities.get(key)
                if isinstance(value, str) and value.strip():
                    cleaned = re.sub(
                        r"^(?:врач|доктор|специалист|кабинет|клиника)\s+",
                        "", value.strip(), flags=re.IGNORECASE,
                    )
                    return cleaned[:_MAX_ENTITY_VALUE_CHARS]

        pending_topic = state.get("pending_active_topic")
        if isinstance(pending_topic, str) and pending_topic.strip():
            return pending_topic.strip()[:_MAX_ENTITY_VALUE_CHARS]
        return None

    @classmethod
    def _query_from_pending_selection(
        cls, facet: str, state: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Turn a short option such as 'телефон'/'кабинет' into a complete retrieval query."""
        labels = {"phone": "Телефон", "cabinet": "Кабинет"}
        label = labels.get(facet)
        if not label:
            return None

        subject = cls._pending_subject(state)
        pending_question = str(state.get("pending_question") or "").strip()
        if subject:
            resolved_query = f"{label} {subject}"
        elif pending_question:
            # Even without a structured person/service entity, retain the complete
            # unresolved question instead of sending the selected noun to retrieval.
            resolved_query = f"{label}: {pending_question.rstrip(' ?!.')}"
        else:
            return None

        entities = state.get("pending_entities")
        if not isinstance(entities, dict) or not entities:
            entities = state.get("entities")
        preserved_entities = dict(entities) if isinstance(entities, dict) else {}
        preserved_entities["requested_attribute"] = facet
        if subject:
            preserved_entities.setdefault("subject", subject)
        return resolved_query[:_MAX_RESOLVED_QUERY_CHARS], preserved_entities

    @staticmethod
    def _facet_label(facet: str, service: dict[str, str]) -> str:
        genitive = service["genitive"]
        if facet == "price":
            facility = "в лабораториях" if service["key"] in {"cbc", "biochemistry"} else "в клиниках"
            alias = " (ФГДС)" if service["key"] == "gastroscopy" else ""
            return f"Стоимость {genitive}{alias}: актуальные цены и диапазон цен {facility}"
        if facet == "preparation":
            return f"Подготовка к {genitive}"
        if facet == "timing":
            return f"Сроки проведения {genitive}"
        if facet == "location":
            return f"Адрес и место проведения {service['name']}"
        if facet == "composition":
            return f"Состав и показатели {genitive}"
        if facet == "contraindications":
            return f"Противопоказания и ограничения для {service['name']}"
        return f"Информация о {genitive}"

    @classmethod
    def _clarification_for_services(
        cls, question: str, services: list[dict[str, str]]
    ) -> str:
        facet = cls._facet_key(question)
        options = [item["name"] for item in services]
        if len(options) >= 2:
            if facet == "price":
                return f"Стоимость какой услуги вас интересует: {options[0]} или {options[1]}?"
            if facet == "preparation":
                return f"Для какой процедуры нужна подготовка: {options[0]} или {options[1]}?"
            return f"Уточните, пожалуйста, к какой услуге относится вопрос: {options[0]} или {options[1]}?"
        return cls._clarification_for(question)

    @classmethod
    def _deterministic_fragment_result(
        cls,
        question: str,
        state: dict[str, Any],
        memory_context: dict[str, Any],
        depends_on_message_id: str | None,
    ) -> ContextualizationResult | None:
        """Resolve common short follow-ups from the latest topic or ask to disambiguate.

        This guard intentionally runs even when the LLM answers, since examples in
        production showed it sometimes returned the raw fragment or picked one of two
        tests without sufficient evidence.
        """
        pending_question = str(state.get("pending_question") or "").strip()
        is_brief_entity_reply = (
            bool(question)
            and "?" not in question
            and len(question.split()) <= 5
            and not re.match(
                r"^(?:что|как|какие|какой|какая|где|когда|сколько|почему|можно|нужно|"
                r"подскажите|уточните|а если)\b",
                question.casefold().strip(),
            )
        )
        if pending_question and is_brief_entity_reply:
            selected_facet = cls._facet_key(question)
            if selected_facet in {"phone", "cabinet"}:
                selected = cls._query_from_pending_selection(selected_facet, state)
                if selected is not None:
                    resolved_query, entities = selected
                    return ContextualizationResult(
                        intent="follow_up",
                        resolved_query=resolved_query,
                        entities=entities,
                        corrections=[], confidence=0.99, clarification_required=False,
                        clarification_question=None, depends_on_message_id=depends_on_message_id,
                        llm_attempted=False, status="resolved_from_clarification_selection",
                    )

            answered_services = cls._candidate_services(question)
            pending_facet = cls._facet_key(pending_question)
            if len(answered_services) == 1 and pending_facet:
                service = answered_services[0]
                return ContextualizationResult(
                    intent="follow_up",
                    resolved_query=cls._facet_label(pending_facet, service),
                    entities={"service": service["name"], "service_key": service["key"]},
                    corrections=[], confidence=0.94, clarification_required=False,
                    clarification_question=None, depends_on_message_id=depends_on_message_id,
                    llm_attempted=False, status="resolved_from_clarification_reply",
                )

        if not cls._is_fragment(question):
            return None

        # Prefer the most recent user message when it explicitly names topics; otherwise
        # use the last normalized request. Do not scan the entire conversation and revive
        # stale topics from earlier turns.
        messages = memory_context.get("messages") or []
        previous_user = next(
            (str(item.get("content") or "").strip() for item in reversed(messages)
             if item.get("role") == "user" and str(item.get("content") or "").strip()),
            "",
        )
        previous_candidates = cls._candidate_services(previous_user)
        state_query = str(state.get("last_resolved_query") or "")
        state_candidates = cls._candidate_services(state_query)
        candidates = previous_candidates if previous_candidates else state_candidates
        if not candidates:
            entities = state.get("entities") if isinstance(state.get("entities"), dict) else {}
            entity_text = " ".join(
                str(entities.get(key) or "")
                for key in cls._ENTITY_KEYS
                if entities.get(key) is not None
            )
            candidates = cls._candidate_services(entity_text or str(state.get("active_topic") or ""))

        if len(candidates) > 1:
            return ContextualizationResult(
                intent="ambiguous", resolved_query=None,
                entities={"candidate_services": [item["name"] for item in candidates]},
                corrections=[], confidence=0.99, clarification_required=True,
                clarification_question=cls._clarification_for_services(question, candidates),
                depends_on_message_id=depends_on_message_id, llm_attempted=False,
                status="clarification_required_multiple_services",
            )
        if len(candidates) == 1:
            facet = cls._facet_key(question)
            if facet:
                service = candidates[0]
                return ContextualizationResult(
                    intent="follow_up",
                    resolved_query=cls._facet_label(facet, service),
                    entities={"service": service["name"], "service_key": service["key"]},
                    corrections=[], confidence=0.94, clarification_required=False,
                    clarification_question=None, depends_on_message_id=depends_on_message_id,
                    llm_attempted=False, status="resolved_from_active_topic",
                )

        return ContextualizationResult(
            intent="ambiguous", resolved_query=None, entities={}, corrections=[],
            confidence=0.0, clarification_required=True,
            clarification_question=cls._clarification_for(question),
            depends_on_message_id=depends_on_message_id, llm_attempted=False,
            status="clarification_required_unresolved_fragment",
        )

    @staticmethod
    def _apply_obvious_typos(question: str, resolved_query: str | None) -> tuple[str, list[dict[str, str]]]:
        value = resolved_query or question
        source_text = f"{question}\n{value}"
        corrections: list[dict[str, str]] = []
        for original, corrected in _OBVIOUS_TYPO_REPLACEMENTS:
            pattern = re.compile(re.escape(original) + r"(?![а-яё])", re.IGNORECASE)
            if pattern.search(source_text):
                value = pattern.sub(corrected, value)
                corrections.append({"original": original, "corrected": corrected, "source": "rule"})
        return value, corrections

    @staticmethod
    def _normalise_question(question: str) -> str:
        return re.sub(r"\s+", " ", (question or "").strip())[:_MAX_QUESTION_CHARS]

    def _load_state(self, conversation_id: str) -> dict[str, Any]:
        """Load the last resolved topic and retain a pending clarification if present."""
        with get_connection() as conn:
            latest = conn.execute(
                """
                SELECT raw_question, resolved_query, resolved_entities, active_topic,
                       clarification_required, clarification_question, intent
                FROM conversation_query_context
                WHERE conversation_id = %s
                ORDER BY created_at DESC, query_id DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
            resolved = conn.execute(
                """
                SELECT resolved_query, resolved_entities, active_topic
                FROM conversation_query_context
                WHERE conversation_id = %s
                  AND resolved_query IS NOT NULL
                  AND clarification_required = FALSE
                ORDER BY created_at DESC, query_id DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
        state: dict[str, Any] = {}
        if resolved:
            entities = self._decode_json(resolved[1], {})
            state.update(
                {
                    "last_resolved_query": resolved[0],
                    "entities": entities if isinstance(entities, dict) else {},
                    "active_topic": resolved[2],
                }
            )
        if latest and bool(latest[4]):
            pending_entities = self._decode_json(latest[2], {})
            state["pending_question"] = str(latest[0] or "")
            state["pending_entities"] = (
                pending_entities if isinstance(pending_entities, dict) else {}
            )
            state["pending_active_topic"] = str(latest[3] or "") or None
            state["pending_clarification_question"] = str(latest[5] or "")
            state["pending_intent"] = str(latest[6] or "ambiguous")
        return state

    @staticmethod
    def _last_user_message_id(conversation_id: str) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM chat_messages
                WHERE conversation_id = %s AND role = 'user'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
        return str(row[0]) if row else None

    def _call_model(
        self,
        question: str,
        memory_context: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        settings = get_settings()
        history_limit = max(1, min(8, int(getattr(settings, "memory_recent_messages", 8))))
        history_chars = max(
            100, min(900, int(getattr(settings, "rag_max_history_message_chars", 600)))
        )
        recent_messages = (memory_context.get("messages") or [])[-history_limit:]
        history = [
            {
                "role": str(message.get("role") or "unknown"),
                "content": str(message.get("content") or "")[-history_chars:],
            }
            for message in recent_messages
        ]
        payload = {
            "current_question": question,
            "recent_messages": history,
            "long_term_summary": str(memory_context.get("summary") or "")[-1000:],
            "last_resolved_query": state.get("last_resolved_query"),
            "active_topic": state.get("active_topic"),
            "resolved_entities": state.get("entities") or {},
            "pending_question": state.get("pending_question"),
            "pending_clarification_question": state.get("pending_clarification_question"),
        }
        raw = self.gigachat.chat_messages(
            [
                {"role": "system", "content": _CONTEXTUALIZER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                },
            ]
        )
        return self._extract_json(raw)

    @classmethod
    def _result_from_payload(
        cls,
        payload: dict[str, Any],
        question: str,
        depends_on_message_id: str | None,
    ) -> ContextualizationResult:
        raw_intent = str(payload.get("intent") or "new_question").strip().casefold()
        intent = raw_intent if raw_intent in _ALLOWED_INTENTS else "new_question"
        raw_query = payload.get("resolved_query")
        resolved_query = (
            str(raw_query).strip()[:_MAX_RESOLVED_QUERY_CHARS]
            if isinstance(raw_query, str) and raw_query.strip()
            else None
        )
        try:
            confidence = float(payload.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(1.0, max(0.0, confidence))
        clarification_required = bool(payload.get("clarification_required", False))
        clarification_question = payload.get("clarification_question")
        if isinstance(clarification_question, str):
            clarification_question = clarification_question.strip()[:500] or None
        else:
            clarification_question = None
        entities = cls._clean_entities(payload.get("entities"))
        corrections = cls._clean_corrections(payload.get("corrections"))

        if intent == "ambiguous":
            clarification_required = True
        if resolved_query is None:
            if intent in {"new_question", "out_of_scope"}:
                # A complete standalone request can safely fall back to its original wording.
                resolved_query = question
            else:
                clarification_required = True
        if intent == "follow_up" and confidence < _CONFIDENCE_THRESHOLD:
            clarification_required = True
        if clarification_required:
            resolved_query = None
            clarification_question = clarification_question or cls._clarification_for(question)

        return ContextualizationResult(
            intent=intent,
            resolved_query=resolved_query,
            entities=entities,
            corrections=corrections,
            confidence=confidence,
            clarification_required=clarification_required,
            clarification_question=clarification_question,
            depends_on_message_id=depends_on_message_id,
            llm_attempted=True,
            status="ok",
        )

    @classmethod
    def _fallback_result(
        cls,
        question: str,
        state: dict[str, Any],
        memory_context: dict[str, Any],
        depends_on_message_id: str | None,
    ) -> ContextualizationResult:
        messages = memory_context.get("messages") or []
        previous_user = next(
            (
                str(item.get("content") or "").strip()
                for item in reversed(messages)
                if item.get("role") == "user" and str(item.get("content") or "").strip()
            ),
            None,
        )
        has_context = bool(state.get("last_resolved_query") or previous_user)
        if cls._is_fragment(question) and not has_context:
            return ContextualizationResult(
                intent="ambiguous",
                resolved_query=None,
                entities={},
                corrections=[],
                confidence=0.0,
                clarification_required=True,
                clarification_question=cls._clarification_for(question),
                depends_on_message_id=depends_on_message_id,
                llm_attempted=True,
                status="fallback_no_context",
            )
        if cls._is_fragment(question) and has_context:
            topic = cls._topic_from_state(state) or previous_user or "предыдущая тема диалога"
            resolved = f"{question.rstrip(' ?.!,;:')} (контекст предыдущего запроса: {topic})"
            return ContextualizationResult(
                intent="follow_up",
                resolved_query=resolved[:_MAX_RESOLVED_QUERY_CHARS],
                entities=state.get("entities") or {},
                corrections=[],
                confidence=0.61,
                clarification_required=False,
                clarification_question=None,
                depends_on_message_id=depends_on_message_id,
                llm_attempted=True,
                status="fallback_with_context",
            )
        return ContextualizationResult(
            intent="new_question",
            resolved_query=question,
            entities={},
            corrections=[],
            confidence=0.5,
            clarification_required=False,
            clarification_question=None,
            depends_on_message_id=depends_on_message_id,
            llm_attempted=True,
            status="fallback_original_question",
        )

    @staticmethod
    def _active_topic(entities: dict[str, Any]) -> str | None:
        for key in LLMContextualizer._ENTITY_KEYS:
            value = entities.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:_MAX_ENTITY_VALUE_CHARS]
        return None

    def _save_result(
        self,
        conversation_id: str,
        query_id: str,
        raw_question: str,
        result: ContextualizationResult,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversation_query_context (
                    query_id, conversation_id, raw_question, resolved_query, intent,
                    resolved_entities, corrections, confidence, clarification_required,
                    clarification_question, depends_on_message_id, active_topic, status
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (query_id) DO UPDATE SET
                    raw_question = EXCLUDED.raw_question,
                    resolved_query = EXCLUDED.resolved_query,
                    intent = EXCLUDED.intent,
                    resolved_entities = EXCLUDED.resolved_entities,
                    corrections = EXCLUDED.corrections,
                    confidence = EXCLUDED.confidence,
                    clarification_required = EXCLUDED.clarification_required,
                    clarification_question = EXCLUDED.clarification_question,
                    depends_on_message_id = EXCLUDED.depends_on_message_id,
                    active_topic = EXCLUDED.active_topic,
                    status = EXCLUDED.status
                """,
                (
                    query_id,
                    conversation_id,
                    raw_question,
                    result.resolved_query,
                    result.intent,
                    json.dumps(result.entities, ensure_ascii=False),
                    json.dumps(result.corrections, ensure_ascii=False),
                    result.confidence,
                    result.clarification_required,
                    result.clarification_question,
                    result.depends_on_message_id,
                    self._active_topic(result.entities),
                    result.status,
                ),
            )
            conn.commit()

    def resolve(
        self,
        current_question: str,
        memory_context: dict[str, Any],
        conversation_id: str,
        query_id: str,
    ) -> ContextualizationResult:
        """Normalize query and stop retrieval when a short follow-up is ambiguous."""
        raw_question = str(current_question or "")
        question = self._normalise_question(raw_question)
        self._ensure_storage()
        state = self._load_state(conversation_id)
        depends_on_message_id = self._last_user_message_id(conversation_id)

        # Detect obvious ambiguity before paying for a model call: a price question
        # after comparing OAK and biochemical testing must be clarified, not guessed.
        deterministic = self._deterministic_fragment_result(
            question, state, memory_context, depends_on_message_id
        )
        if deterministic is not None and (
            deterministic.clarification_required
            or deterministic.status in {
                "resolved_from_clarification_reply",
                "resolved_from_clarification_selection",
            }
        ):
            result = deterministic
        else:
            try:
                payload = self._call_model(question, memory_context, state)
                result = self._result_from_payload(payload, question, depends_on_message_id)
            except Exception as exc:  # never make a raw short fragment look resolved
                logger.warning(
                    "LLM contextualization failed; using a conservative fallback: %s", exc
                )
                result = self._fallback_result(
                    question, state, memory_context, depends_on_message_id
                )
            # For a short facet with exactly one recognized active service, keep the
            # LLM call but enforce the stable, standalone query to guard against outputs
            # such as 'previous question: ... follow-up: cost?'.
            if deterministic is not None:
                deterministic.llm_attempted = True
                result = deterministic

        # Normalize a few unambiguous, high-frequency typos after LLM rewriting, while
        # preserving the original user text for history and diagnostics.
        if result.resolved_query:
            corrected_query, typo_corrections = self._apply_obvious_typos(
                question, result.resolved_query
            )
            result.resolved_query = corrected_query[:_MAX_RESOLVED_QUERY_CHARS]
            known = {(item.get("original"), item.get("corrected")) for item in result.corrections}
            for correction in typo_corrections:
                if (correction["original"], correction["corrected"]) not in known:
                    result.corrections.append(correction)

        # Last defense: do not let a model-supplied unresolved fragment pass through.
        if self._is_fragment(question) and (
            not result.resolved_query or self._is_fragment(result.resolved_query)
        ):
            result.intent = "ambiguous"
            result.resolved_query = None
            result.clarification_required = True
            result.clarification_question = (
                result.clarification_question or self._clarification_for(question)
            )
            result.status = "clarification_required_unresolved_fragment"

        if (
            result.clarification_required
            or result.intent == "ambiguous"
            or not result.resolved_query
        ):
            result.clarification_required = True
            result.resolved_query = None
            result.clarification_question = (
                result.clarification_question or self._clarification_for(question)
            )

        self._save_result(conversation_id, query_id, raw_question, result)
        return result

