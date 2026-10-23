"""Live PostgreSQL smoke test for MedTrust knowledge-gap persistence.

Run from the MedTrust project root:
    python scripts/check_knowledge_gap_registration.py
"""
from __future__ import annotations

import hashlib
import sys
import uuid
from pathlib import Path


# При запуске Python добавляет в sys.path папку scripts/,
# поэтому явно добавляем корень проекта medtrust_solution/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    if not (PROJECT_ROOT / "app").is_dir():
        print(
            f"FAIL: папка app не найдена в корне проекта: {PROJECT_ROOT}",
            file=sys.stderr,
        )
        return 2

    try:
        import psycopg
    except ImportError as exc:
        print(
            f"FAIL: не установлена зависимость PostgreSQL: {exc}. "
            "Установи зависимости проекта в активном .venv.",
            file=sys.stderr,
        )
        return 2

    try:
        from app.services.knowledge_gap_tracker import (
            KnowledgeGapTracker,
            _normalise,
        )
    except ImportError as exc:
        print(
            f"FAIL: не удалось импортировать трекер MedTrust: {exc}. "
            f"Корень проекта: {PROJECT_ROOT}",
            file=sys.stderr,
        )
        return 2

    tracker = KnowledgeGapTracker()
    database_url = tracker.database_url

    if not database_url:
        print(
            "FAIL: URL PostgreSQL не настроен. "
            "Проверь настройки приложения и DATABASE_URL/DATABASE_DSN.",
            file=sys.stderr,
        )
        return 2

    token = uuid.uuid4().hex
    query = f"medtrust временная проверка регистрации пробела {token}"
    fingerprint = hashlib.sha256(
        _normalise(query).encode("utf-8")
    ).hexdigest()

    conversation_id = str(uuid.uuid4())
    query_id_1 = str(uuid.uuid4())
    query_id_2 = str(uuid.uuid4())
    cleanup_needed = False

    try:
        # Дважды записываем один запрос: запись должна обновиться,
        # а occurrence_count должен стать равен 2.
        for attempt, query_id in (
            (1, query_id_1),
            (2, query_id_2),
        ):
            stored = tracker.record_gap(
                query=query,
                reason="automated_registration_smoke_test",
                conversation_id=conversation_id,
                query_id=query_id,
                wiki_candidates=[
                    {
                        "title": "Temporary smoke test",
                        "path": "test/temporary",
                    }
                ],
            )

            if not stored:
                print(
                    f"FAIL: record_gap вернул False на попытке {attempt}. "
                    "Подробности ищи в логах приложения.",
                    file=sys.stderr,
                )
                return 1

            cleanup_needed = True

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        sample_query,
                        reason,
                        occurrence_count,
                        last_conversation_id,
                        last_query_id,
                        wiki_candidates
                    FROM knowledge_gaps
                    WHERE fingerprint = %s
                    """,
                    (fingerprint,),
                )
                row = cur.fetchone()

        if row is None:
            print(
                "FAIL: трекер сообщил об успехе, "
                "но запись в PostgreSQL не найдена.",
                file=sys.stderr,
            )
            return 1

        (
            sample_query,
            reason,
            occurrence_count,
            stored_conversation_id,
            stored_query_id,
            candidates,
        ) = row

        if occurrence_count != 2:
            print(
                "FAIL: ожидалось occurrence_count=2, "
                f"получено {occurrence_count}.",
                file=sys.stderr,
            )
            return 1

        if reason != "automated_registration_smoke_test":
            print(
                f"FAIL: неожиданная причина записи: {reason!r}",
                file=sys.stderr,
            )
            return 1

        if (
            str(stored_conversation_id) != conversation_id
            or str(stored_query_id) != query_id_2
        ):
            print(
                "FAIL: идентификаторы диалога или последнего запроса "
                "не совпадают с ожидаемыми.",
                file=sys.stderr,
            )
            return 1

        if not candidates:
            print(
                "FAIL: Wiki-кандидаты не сохранены в PostgreSQL.",
                file=sys.stderr,
            )
            return 1

        print("PASS: PostgreSQL knowledge-gap registration verified.")
        print(f"sample_query: {sample_query}")
        print(f"occurrence_count after two writes: {occurrence_count}")
        print(f"last_query_id: {stored_query_id}")
        print("Проверка записи и повторного обновления пройдена.")
        return 0

    except Exception as exc:
        print(
            "FAIL: ошибка интеграционной проверки PostgreSQL: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    finally:
        # Удаляем только временную запись этой проверки.
        if cleanup_needed:
            try:
                with psycopg.connect(
                    database_url,
                    connect_timeout=5,
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            DELETE FROM knowledge_gaps
                            WHERE fingerprint = %s
                            """,
                            (fingerprint,),
                        )
                print("Временная тестовая запись удалена.")
            except Exception as exc:
                print(
                    "WARNING: не удалось удалить временную запись. "
                    f"Fingerprint: {fingerprint}. Ошибка: {exc}",
                    file=sys.stderr,
                )


if __name__ == "__main__":
    raise SystemExit(main())