# LangSmith: tracing и retrieval evaluation

MedTrust подключает LangSmith через Python SDK. LangChain не требуется: существующий FastAPI + PostgreSQL/pgvector + GigaChat pipeline остаётся без смены архитектуры.

## 1. Настройка

1. Установите зависимости в активное виртуальное окружение:

   ```powershell
   pip install -r requirements.txt
   ```

2. Скопируйте `.env.example` в `.env` (не перезаписывайте свой действующий `.env`) и заполните `LANGSMITH_API_KEY` ключом из настроек LangSmith.
3. Включите трейсинг:

   ```dotenv
   LANGSMITH_TRACING=true
   LANGSMITH_PROJECT=MedTrust
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   LANGSMITH_TRACE_CONTENT=false
   ```

4. Перезапустите FastAPI. Следующие `/api/v1/query` запросы появятся в проекте `MedTrust` в LangSmith.

Для европейского workspace при необходимости укажите endpoint, предоставленный LangSmith, например `https://eu.api.smith.langchain.com`.

## 2. Что записывается в трассировку

- Корневая операция `MedTrust RAG query` — запрос, `top_k`, наличие контекста диалога, итоговый статус и количество источников.
- `MedTrust hybrid retrieval` — аспекты запроса, ID чанков, пути Wiki, ранги dense/lexical/path, RRF score и признак допустимости использования в ответе.
- `MedTrust RAG context preparation` — какие найденные фрагменты и внешние источники подготовлены для контекста модели.
- `GigaChat completion` — отдельный LLM-span для REST-вызова GigaChat и его длительности/результата.

Фактические вызовы `@traceable` вложены друг в друга; продолжительность фиксируется SDK. Тексты чанков, вопроса и ответа по умолчанию не отправляются: сохраняются хеш и длина.

## 3. Приватность

`LANGSMITH_TRACE_CONTENT=false` — рекомендуемое значение для обычной разработки. Идентификаторы пациента и conversation history не раскрываются в обработчиках prompt-trace; patient context и приватная история редактируются. Не включайте `LANGSMITH_TRACE_CONTENT=true` для реальных обращений пациентов: при таком режиме тексты запросов, ответов и фрагментов Wiki могут отправляться в облако LangSmith. Для демонстрации используйте синтетические/обезличенные данные и соблюдайте правила вашей организации.

Если `LANGSMITH_TRACING=false`, SDK не создаёт отправляемые trace runs и MedTrust продолжает работать как раньше. Если ключ пустой или SDK отсутствует, трейсинг отключается с предупреждением в логах.

## 4. Загрузка Golden Set v1 как LangSmith Dataset

Из корня проекта выполните:

```powershell
python scripts/export_golden_set_to_langsmith.py --dry-run
python scripts/export_golden_set_to_langsmith.py
```

Экспортёр создаёт датасет `MedTrust Golden Set v1 — Retrieval` (или имя из `LANGSMITH_DATASET_NAME`) и добавляет недостающие кейсы, сверяясь с `metadata.case_id`. Он передаёт только тестовый вопрос, `top_k`, ожидаемые пути документов и категориальные метаданные. Содержимое `.env`, история диалогов, пациентские данные и live API-ответы не экспортируются. Повторный запуск не дублирует уже загруженные кейсы.

Golden Set v1 содержит эталонные **пути документов**, но не размеченные `chunk_id`. Поэтому платформа оценивает retrieval на уровне уникальных Wiki-документов; повторяющиеся чанки одного документа не увеличивают количество релевантных результатов.

## 5. Retrieval metrics в локальном Golden Set runner

Запуск оценки по работающему API:

```powershell
python tests/evaluation/run_evaluation.py --base-url http://127.0.0.1:8000 --top-k 5
```

Отчёт дополняется средними метриками по кейсам, у которых заданы `expected_source_paths`:

- **Precision@K** — доля релевантных уникальных документов в первых K позициях (знаменатель фиксирован и равен K).
- **Recall@K** — доля ожидаемых документов, найденных в первых K позициях.
- **MRR@K** — обратный ранг первого ожидаемого документа.
- **nDCG@K** — качество порядка ранжирования ожидаемых документов.

Это отдельные retrieval-метрики: существующий балл Golden Set за качество ответа и его pass/fail gate не изменяются. Cases с отсутствующей ожидаемой документацией не включаются в усреднение этих метрик.

## 6. Проверка интеграции

1. Проверьте, что API запускается с `LANGSMITH_TRACING=true` и API key задан.
2. Отправьте тестовый вопрос через Swagger `/docs` или `Invoke-RestMethod`.
3. Откройте LangSmith → Projects → `MedTrust`: корневая RAG-трассировка должна содержать retrieval, context preparation и GigaChat spans.
4. Откройте Datasets и проверьте наличие 49 примеров Golden Set.
5. Запустите локальный Golden Set runner и проверьте новые retrieval metrics в Markdown/JSON отчёте.
