# MedTrust — LLM Contextualizer / Query Rewriting

Патч рассчитан на актуальную локальную версию MedTrust с последними правками RAG и web-search. Он не заменяет весь `rag.py`, чтобы не затереть изменения v30/v31.

## Состав архива

- `app/services/contextualizer.py` — новый LLM Contextualizer, JSON-контракт, безопасный fallback и сохранение нормализации в PostgreSQL.
- `scripts/apply_contextualizer_patch.py` — интегрирует Contextualizer в существующий `app/services/rag.py` в проверенных точках.
- `tests/test_contextualizer.py` — регрессионные тесты контракта и неоднозначных коротких вопросов.

## Применение

1. Распаковать архив в корень `medtrust_solution`, сохранив структуру каталогов.
2. Из корня проекта выполнить: `python scripts/apply_contextualizer_patch.py`.
3. Скрипт создаст резервную копию `app/services/rag.py.pre_contextualizer.bak` и добавит интеграцию.
4. Перезапустить FastAPI. Новая таблица `conversation_query_context` создаётся автоматически при первом запросе; существующие документы Wiki и индексы не меняются.
5. Проверить тесты командой `pytest -q tests/test_contextualizer.py`.

Скрипт не применяет изменения, если не находит ожидаемые уникальные фрагменты в `rag.py`, и оставляет файл нетронутым. Повторный запуск после успешной установки безопасен.

## Изменения

- История ограничивается настройками `memory_recent_messages` и `rag_max_history_message_chars`; отдельный профиль пациента Contextualizer не получает.
- В историю поиска поступает самостоятельный `resolved_query`, а не исходный короткий фрагмент.
- Исходный вопрос и нормализованный запрос сохраняются отдельно вместе с intent, сущностями, corrections, confidence и зависимостью от предыдущего сообщения.
- Если объект короткого вопроса не восстановлен уверенно, приложение возвращает уточнение и прекращает обработку до выполнения Wiki/web-поиска.
- При сбое Contextualizer полный самостоятельный вопрос направляется в поиск без изменения; короткий фрагмент без контекста переводится в запрос уточнения.
- В prompt генератора ответа передаются и исходный вопрос, и `resolved_query`. Сам `resolved_query` не считается доказательством медицинского утверждения.

# MedTrust — карта пробелов в Wiki, MVP (этапы 1–2)

Архив содержит только файлы для копирования по тем же путям в корень `medtrust_solution`:

- `app/services/rag.py` — строже проверяет, покрывает ли Wiki именно запрошенный аспект; наличие общего документа о процедуре больше не считается достаточным для вопроса о цене или противопоказаниях. При недостаточности сохраняет пробел **до** вызова web-search.
- `app/services/knowledge_gap_tracker.py` — создаёт таблицу `knowledge_gaps` при первом пробеле и идемпотентно обновляет запись по нормализованному запросу. Повторные вопросы увеличивают `occurrence_count`, а не создают дубликаты.
- `tests/test_knowledge_gap_tracker.py` — базовые тесты нормализации и поведения без настроенного подключения к БД.

## Проверка

```powershell
python -m py_compile app/services/rag.py app/services/knowledge_gap_tracker.py
pytest -q tests/test_knowledge_gap_tracker.py
```

Таблица создаётся автоматически в PostgreSQL при первом запросе, для которого Wiki признана недостаточной. Дополнительный скрипт миграции запускать не нужно. Используется URL подключения из настроек приложения (`database_url`, `database_dsn`, `postgres_dsn`, `db_url`) либо `DATABASE_URL`/`DATABASE_DSN`.

Запись пробела работает в best-effort режиме: если БД временно недоступна или URL не найден, основной RAG и web-search продолжают работу, ошибка фиксируется в логе.

Это MVP, а не полный административный модуль: статус пробела сейчас по умолчанию `open`; интерфейс обработки, объединение семантически похожих формулировок и пользовательская обратная связь в этот патч не входят.

# MedTrust — правки формулировок, форматирования и проверка регистрации пробелов

Архив содержит файлы по путям относительно корня `medtrust_solution`. Распакуйте архив в корень проекта с заменой соответствующих файлов.

## Что исправлено

- **Формулировка при недостатке доказательств:** ответ больше не утверждает, что «проверенные веб-источники» были найдены и проверены, если система фактически не получила подтверждающий материал. Используется точная формулировка: «среди доступных веб-результатов не удалось найти источник, подтверждающий…».
- **Нумерация списков:** элементы одного Markdown-списка остаются пронумерованы последовательно, даже если между пунктами стоят пустые строки. Новый обычный абзац или заголовок начинает новый список.
- Правила форматирования и безопасные сообщения вынесены в `app/services/answer_presentation.py`, чтобы их можно было тестировать отдельно.
- Добавлен `scripts/check_knowledge_gap_registration.py` — **проверка реального подключения к PostgreSQL**. Она создаёт случайную временную запись через `KnowledgeGapTracker`, отправляет тот же запрос повторно, проверяет одну запись с `occurrence_count = 2`, сверяет идентификаторы и JSON с кандидатами Wiki, а затем удаляет только созданную ею временную запись.

## Локальные тесты без подключения к PostgreSQL

Из корня проекта:

```powershell
python -m py_compile app/services/rag.py app/services/answer_presentation.py app/services/knowledge_gap_tracker.py scripts/check_knowledge_gap_registration.py
pytest -q tests/test_answer_presentation.py tests/test_web_evidence_guard.py tests/test_knowledge_gap_tracker.py
```

## Проверка фактической регистрации в PostgreSQL

Запустите из корня проекта в том же окружении, где настроен `.env` приложения:

```powershell
python scripts/check_knowledge_gap_registration.py
```

Ожидаемый успешный вывод содержит:

```text
PASS: PostgreSQL knowledge-gap registration verified.
occurrence_count after two writes: 2
Temporary smoke-test row will be removed.
```

Если скрипт сообщает, что URL БД не настроен, проверьте параметры в `app.core.config` или переменные `DATABASE_URL` / `DATABASE_DSN`. Если сообщает об ошибке подключения или SQL, запись в PostgreSQL не подтверждена.

### Проверка записей по трём ручным запросам

Скрипт выше проверяет весь путь записи и дедупликации на временном запросе. Чтобы посмотреть пробелы, обнаруженные при ручных проверках цены гастроскопии и противопоказаний к МРТ, выполните в PostgreSQL:

```sql
SELECT
    sample_query,
    reason,
    occurrence_count,
    first_seen_at,
    last_seen_at,
    last_conversation_id,
    last_query_id,
    wiki_candidates
FROM knowledge_gaps
WHERE sample_query ILIKE '%гастроскоп%'
   OR sample_query ILIKE '%мрт%'
   OR sample_query ILIKE '%противопоказ%'
ORDER BY last_seen_at DESC
LIMIT 30;
```

Эти ручные запросы будут присутствовать в таблице лишь в том случае, если для них действительно сработало ветвление регистрации пробела, а запись прошла успешно. Контрольный запрос про острую травму колена не обязан создавать пробел, если Wiki полностью покрывает вопрос.

## Границы проверки

Unit-тесты не подтверждают подключение к вашему локальному PostgreSQL. Интеграционная проверка считается пройденной только после запуска `scripts/check_knowledge_gap_registration.py` в вашем MedTrust-окружении. В рабочей среде подготовки патча нет доступного сервера PostgreSQL и модуля `psycopg`, поэтому фактическую запись в БД оттуда проверить невозможно.

# MedTrust: отдельный ручной веб-поиск

Распаковать в корень `medtrust_solution`, заменив `app/api/routes.py`. `app/main.py` менять не нужно.

Новый эндпоинт: `POST /api/v1/web-search`.

Пример тела в Swagger (`http://127.0.0.1:8000/docs`):

```json
{"question":"Какие противопоказания к МРТ с контрастированием?","limit":5}
```

Эндпоинт использует SearXNG и GigaChat, без Wiki, RagService, KnowledgeGapTracker и записи в БД. В отличие от стандартного поиска, он **не отбрасывает источники по тематической релевантности**, но сохраняет проверку безопасности URL (HTTPS и allowlist). Ответ формируется по полученным материалам, включая слабые, с предупреждением в конце. Источники содержат `relevance` и `evidence_status`.

Ограничение: если SearXNG не вернул разрешённых URL, содержательный ответ не гарантирован. Доступность GigaChat/SearXNG в этом окружении не проверялась. Стандартный `/api/v1/query` не изменён.


# MedTrust: `/api/v1/query` только по локальной Wiki

## Что изменено

- `/api/v1/query` больше не создаёт клиент SearXNG и не вызывает веб-поиск.
- Поиск документов по-прежнему выполняется через локальный hybrid search PostgreSQL/pgvector.
- GigaChat формирует ответ только по найденным фрагментам Wiki. Если подходящих источников нет, система не просит модель отвечать из общих знаний.
- Сохранены `conversation_id`, contextualizer, атрибуция утверждений источникам и `KnowledgeGapTracker`.
- Для запросов об актуальных рекомендациях в ответе и диагностике явно отмечается, что внешняя актуальность не проверялась.
- Убраны автоматические ссылки PubMed/NHS/NICE, которые раньше добавлялись как запасной вариант при недостатке локальных источников.
- Формат ответа сохраняет поля совместимости: `web_search_attempted=false`, `web_search_used=false`, `web_search_status="not_attempted"`; добавлено `web_search_policy="disabled_for_query_endpoint"`.
- `routes.py` и отдельный `POST /api/v1/web-search` не меняются.

## Совместимость

Файл `rag.py` собран на основе версии MedTrust, в которой уже есть `app/services/contextualizer.py`, `app/services/knowledge_gap_tracker.py` и `app/services/web_evidence_guard.py`. Не заменяйте им заметно отличающуюся версию `rag.py` без сравнения изменений.

## Установка в PowerShell

Запустите команды из корня репозитория. Сначала создайте резервные копии:

```powershell
Copy-Item .\app\services\rag.py .\app\services\rag.py.bak
Copy-Item .\app\services\answer_presentation.py .\app\services\answer_presentation.py.bak
```

Распакуйте архив во временную папку и скопируйте файлы приложения:

```powershell
Expand-Archive -Path .\medtrust_query_db_only_patch.zip -DestinationPath .\medtrust_query_db_only_patch -Force
Copy-Item .\medtrust_query_db_only_patch\app\services\rag.py .\app\services\rag.py -Force
Copy-Item .\medtrust_query_db_only_patch\app\services\answer_presentation.py .\app\services\answer_presentation.py -Force
Copy-Item .\medtrust_query_db_only_patch\tests\test_answer_presentation.py .\tests\test_answer_presentation.py -Force
Copy-Item .\medtrust_query_db_only_patch\tests\test_query_database_only_policy.py .\tests\test_query_database_only_policy.py -Force
```

Затем выполните `pytest -q` и перезапустите FastAPI. Ручку `/api/v1/query` проверьте запросом, по которому в Wiki есть документы, и запросом, по которому их нет. Для обоих случаев в ответе должно быть `web_search_attempted: false`. Отдельно проверьте `POST /api/v1/web-search`, который продолжает использовать собственный сервис.
