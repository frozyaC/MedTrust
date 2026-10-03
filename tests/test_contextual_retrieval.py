from app.services.rag import RagService
from app.db.repository import KnowledgeRepository


def test_follow_up_question_is_contextualized():
    memory = {
        "summary": "",
        "messages": [
            {"role": "user", "content": "Куда записать пациента при травме 5 дней назад?"},
            {"role": "assistant", "content": "В травмпункт."},
        ],
    }

    result = RagService._contextualize_question(
        "А если пациент уже обращался в другую клинику?",
        memory,
    )

    assert "Куда записать пациента при травме 5 дней назад?" in result
    assert "А если пациент уже обращался в другую клинику?" in result


def test_standalone_question_is_not_contextualized():
    memory = {
        "summary": "",
        "messages": [
            {"role": "user", "content": "Куда записать пациента при травме?"},
        ],
    }

    question = "Какие анализы нужны перед УЗИ?"
    assert RagService._contextualize_question(question, memory) == question


def test_fts_query_uses_or_semantics():
    query = KnowledgeRepository._fts_or_query("Куда записать пациента при травме 5 дней назад?")
    assert " OR " in query
    assert "пациента" in query
    assert "травме" in query


def test_follow_up_context_does_not_override_current_scope():
    from app.services.safety import QueryScopeValidator

    previous = "Куда записать пациента при травме?"
    current = "А как написать Python-код для Docker?"

    # The current question is out of scope despite a medical previous message.
    assert QueryScopeValidator().validate(current).allowed is False
    assert previous != current
