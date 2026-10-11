# MedTrust — Path-Aware Hybrid RAG Backend

MVP backend для интеллектуального справочника регистратора. В проекте реализованы path-aware ingestion из Wiki.js Markdown, Qwen embeddings, PostgreSQL/pgvector + FTS, weighted RRF, GigaChat, долгосрочная память диалога, web-search fallback и тематический scope guard.

## Архитектура

```text
Frontend chat
     |
     v
POST /api/v1/query
     |
     +--> scope guard
     +--> conversation_id -> PostgreSQL memory
     +--> contextualize follow-up
     +--> Qwen Embedding
     |       |
     |       +--> pgvector dense search
     |       +--> PostgreSQL FTS
     |       +--> path retrieval
     |                |
     |                v
     |              weighted RRF
     |
     +--> answerability gate
             |
       +-----+-----+
       |           |
      Wiki       weak Wiki
       |           |
       |        Web Search
       |           |
       +-----+-----+
             |
             v
         GigaChat
             |
             v
 answer + used sources + retrieval diagnostics
```

## Path-aware Wiki.js

В предоставленном `Суфлёр.zip` физическая папка не отражает всю логическую структуру. Источник структуры — поле `Путь:` внутри Markdown. Например:

```text
Путь: Регистратура/Словарь/Травматология/Общая_информация
```

Путь сохраняется как raw hierarchy и участвует в embedding text и path lexical signal. Поэтому `Регистратура/Словарь/Травматология` отличается от `Регистратура/Скрипты` не только URL, но и типом знания.

## Long-term memory и `conversation_id`

История хранится в PostgreSQL в таблицах `conversations`, `chat_messages`, `conversation_memory`.

Первый запрос:

```json
{
  "question": "Куда записать пациента при травме 5 дней назад?",
  "patient": null,
  "top_k": 5,
  "conversation_id": null
}
```

Backend создаёт `conversation_id` и возвращает его.

Frontend должен сохранить этот идентификатор и передавать его во все последующие запросы одного чата:

```json
{
  "question": "А если пациент уже обращался в другую клинику?",
  "conversation_id": "262298dd-fa67-4427-b4f1-8f10b4c03a0b"
}
```

По `conversation_id` backend загружает историю из PostgreSQL. Для follow-up вопросов формируется отдельный contextualized retrieval query, поэтому короткий вопрос не теряет объект предыдущего сообщения:

```text
Q1: Куда записать пациента при травме 5 дней назад?
Q2: А если пациент уже обращался в другую клинику?

Retrieval query:
Предыдущий вопрос: Куда записать пациента при травме 5 дней назад?
Уточняющий текущий вопрос: А если пациент уже обращался в другую клинику?
```

В GigaChat передаются summary и последние сообщения, а не неограниченная история.

## Web-search fallback

Web-search запускается только после проверки Wiki.js. Если лучший Wiki-кандидат недостаточно релевантен, backend обращается к локальному SearXNG, запущенному в Docker. API key для SearXNG не нужен.

Архитектура: `MedTrust → SearXNG → поисковые движки → WEB1..WEB3 → GigaChat`. SearXNG возвращает результаты через JSON API `/search?q=...&format=json`; в локальной конфигурации формат `json` включён в `searxng/settings.yml`.

Внешний поиск получает только contextualized question, без structured patient context. После поиска применяются правила:

1. сначала выполняется обычный поиск;
2. только HTTPS;
3. host должен совпасть с `WEB_SAFE_DOMAINS` или его поддоменом;
4. если безопасных результатов недостаточно, выполняется дополнительный поиск через `site:` по авторитетным доменам из `WEB_FALLBACK_DOMAINS`;
5. парсер собирает расширенный пул кандидатов (до 15, при необходимости до 30), а не прекращает поиск после первых трёх безопасных URL;
6. доменные fallback-запросы для известных медицинских тем используют англоязычные поисковые термины, чтобы повысить recall по NICE/PubMed при вопросах на русском языке;
7. заголовок и сниппет используются для отбрасывания явных противоречий, но отсутствие нужного термина в метаданных не считается достаточной причиной отказа: неоднозначные безопасные страницы ограниченно загружаются и проходят финальную проверку по полному тексту и типу запроса;
8. нерелевантные страницы исключаются до передачи источников в GigaChat; `RagService` повторно проверяет их перед генерацией и включением в `sources`;
9. после фильтрации выбираются максимум три результата: `WEB1`, `WEB2`, `WEB3`; при ошибке загрузки используется исходный поисковый сниппет, HTTP-редиректы при обогащении не следуются.

### Точный тест web-search

Для тестовой Wiki тема мигрени отсутствует. В `.env` должны быть:

```env
WEB_SEARCH_ENABLED=true
SEARXNG_URL=http://127.0.0.1:8080
WEB_SEARCH_TIMEOUT_SECONDS=15
WEB_SEARCH_FALLBACK_TIMEOUT_SECONDS=8
WEB_SEARCH_LANGUAGE=ru
WEB_FALLBACK_MAX_DOMAINS=4
WEB_FALLBACK_DOMAINS=nice.org.uk,pubmed.ncbi.nlm.nih.gov,cr.minzdrav.gov.ru,who.int
WEB_SOURCE_MAX_CHARS=6000
```

Запустить PostgreSQL и SearXNG:

```powershell
docker compose up -d db searxng
```

Проверить SearXNG в браузере:

```text
http://127.0.0.1:8080
```

Или проверить JSON API:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/search?q=мигрень&format=json"
```

В Swagger `http://127.0.0.1:8000/docs` выполнить `POST /api/v1/query`:

```json
{
  "question": "Какие современные рекомендации по диагностике мигрени у взрослых?",
  "patient": null,
  "top_k": 5,
  "conversation_id": null
}
```

При доступном SearXNG и наличии безопасных **и релевантных** результатов (в том числе найденных через доменный fallback) признаки успешного fallback:

```json
"web_search_attempted": true,
"web_search_used": true,
"web_search_status": "success"
```

Если поисковые движки возвращают безопасные, но не относящиеся к вопросу страницы, ожидается `web_search_status: "no_relevant_results"`, пустой массив `sources` и ответ `Данных может быть недостаточно.` — неподходящие источники не должны цитироваться. При этом отсутствие темы в коротком сниппете само по себе не должно приводить к отказу: backend проверяет ограниченный пул страниц после обогащения полным текстом.

В `sources` должны появиться использованные моделью веб-источники `[WEB1]`, `[WEB2]` и т. п. Если SearXNG недоступен, результаты не проходят allowlist или сами поисковые движки не возвращают подходящих страниц, backend не подменяет это выдуманным ответом и возвращает `Данных может быть недостаточно.`.

Подробнее: `docs/WEB_SEARCH.md`.

## Sources

`/api/v1/query` возвращает `sources` только для источников, чьи citation markers (`[W1]`, `[WEB1]`) реально присутствуют в ответе модели. Если Wiki.js не прошёл answerability gate, нерелевантные Wiki-фрагменты не передаются GigaChat как доказательство: в prompt остаются только safe web-источники.

`retrieval` — отладочный массив с `dense_rank`, `lexical_rank`, `path_rank`, `dense_similarity`, `rrf_score` и `eligible_for_answer`: `false` означает, что фрагмент найден поиском, но не передаётся модели как доказательство.

Wiki URL не выдумываются: в предоставленном архиве есть Wiki.js links внутри текста, но не отдельный canonical URL страницы. Если ingestion получает `URL:`, `Источник:` или `Source-URL:`, он сохраняет его как `source_url`.

## Scope guard

Запрос проверяется до retrieval. Разрешаются медицинские вопросы, темы клиники и запросы про содержимое Wiki.js. Явно нерелевантные темы блокируются.

Это MVP rule-based guardrail. Перед production рекомендуется провести отдельную разметку и evaluation набора реальных запросов.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | DB health |
| POST | `/api/v1/knowledge/reindex` | ZIP → chunks → embeddings → DB |
| POST | `/api/v1/search` | retrieval diagnostics without LLM |
| POST | `/api/v1/query` | full RAG + memory + web fallback |
| POST | `/api/v1/conversations` | create chat |
| GET | `/api/v1/conversations` | list chats |
| GET | `/api/v1/conversations/{conversation_id}` | chat + history |
| GET | `/api/v1/conversations/{conversation_id}/messages` | history |
| GET | `/api/v1/knowledge/{document_id}` | document metadata |
| POST | `/api/v1/feedback` | registrar feedback |

## Run

```powershell
docker compose up -d db searxng
```

PostgreSQL: `localhost:5433`, so it does not conflict with ALGSCC on `localhost:5432`.

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

## GigaChat

REST flow:

```text
POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth
        ↓ access_token
POST https://api.giga.chat/v1/chat/completions
```

`GIGACHAT_VERIFY_SSL=false` оставлен для локальной разработки при проблемах доверенного CA. Для production следует использовать доверенный CA bundle.

## Secrets

`.env` не должен попадать в Git. В репозитории хранится только `.env.example`.

## Последнее изменение: v8 — контроль целостности цитат

Если Wiki.js не проходит answerability gate, его фрагменты не передаются в prompt и не могут появиться в списке источников ответа. GigaChat получает только разрешённые метки `WEB1..WEB3`. Backend также отклоняет ответ, содержащий цитату, которой нет среди реально переданных источников.

## Качество медицинских ответов и бюджет ресурсов (v19)

По умолчанию запрос выполняет **один вызов GigaChat для генерации** после retrieval; отдельные model-вызовы для review/repair отключены, чтобы не тратить дополнительные токены на повторение одного и того же ответа. После генерации запускаются ограниченные детерминированные проверки цитат, чисел и единиц, возрастной группы, отдельных ошибок в описании ауры, неподдержанных клинических утверждений и полноты ответа по сведениям, которые реально присутствуют в источниках. Если проверка не пройдена, система возвращает ограниченный фрагмент источника или сообщение о недостаточности данных, не вызывая модель повторно.

`answer_reviewed=true` означает только прохождение реализованных автоматических проверок, а не гарантию клинической правильности. Проверка основана на конкретных шаблонах и не заменяет независимую клиническую оценку.

По умолчанию ограничены ресурсы на запрос:

- `GIGACHAT_MAX_TOKENS=450` — максимум токенов ответа модели;
- `RAG_MAX_WEB_SOURCES=2` — не более двух веб-источников;
- `RAG_MAX_WIKI_SOURCES=3` — не более трёх подходящих фрагментов Wiki.js;
- `RAG_MAX_SOURCE_CHARS=4200` — предел длины текста каждого источника;
- `RAG_MAX_HISTORY_MESSAGES=4`, `RAG_MAX_HISTORY_MESSAGE_CHARS=600` — ограниченная история в prompt;
- `MEMORY_SUMMARY_ENABLED=false` — дополнительные вызовы GigaChat для резюме переписки выключены.

Обычный запрос с найденными источниками выполняет один вызов embeddings API и один вызов GigaChat. Для конкретного FAQ о диагностике мигрени у взрослых, когда извлечены необходимые разделы NICE, используется компактный шаблон ответа по источнику и вызов GigaChat не нужен (`gigachat_calls=0`). Запрос, отклонённый scope guard, или запрос без подходящих источников тоже может завершиться без вызова GigaChat. Поле `resource_usage` показывает число вызовов, лимит вывода и фактические токены GigaChat, если провайдер вернул `usage`; иначе возвращается оценка входных токенов. Токены embeddings показываются отдельно, если Cloud.ru вернул соответствующую метаинформацию. Оценки не являются биллинговым отчётом.

Цель precision, recall и accuracy выше 0.95 остаётся неподтверждённой до проверки на размеченном наборе с независимой клинической оценкой; определения метрик и протокол приведены в `docs/MEDICAL_QA_EVALUATION.md`.


### Полный текст клинических рекомендаций NICE

Когда SearXNG возвращает обзор NICE вместо содержательного раздела, MedTrust автоматически получает страницу `/guidance/<id>/chapter/recommendations` для запросов о диагностике, лечении, симптомах или рекомендациях. Парсер отдаёт RAG основной текст страницы, а не только обзорный сниппет; ссылки в `sources` ведут на фактически использованный раздел. Для вопроса о диагностике мигрени у взрослых при наличии полного набора разделов используется краткий шаблон без вызова GigaChat; если доступен лишь короткий фрагмент таблицы, ответ ограничивается подтверждёнными признаками боли и явно предупреждает, что полного текста недостаточно.


### Диагностика и контроль расходов (v19)

`POST /api/v1/query` возвращает `answer_review_diagnostics` и `resource_usage`. `answer_review_diagnostics.stage` и `status` показывают, прошёл ли ответ детерминированные проверки, а `initial_issues`/`final_issues` содержат найденные замечания. Поля `reviewed_issues` и `repaired_issues` сохранены для совместимости формата, но при стандартном однопроходном режиме остаются пустыми: отдельные вызовы GigaChat для review и repair не выполняются. `attempts.quality_review`, `attempts.content_repair` и `attempts.citation_retry` должны быть равны `0`.

В `resource_usage` выводятся `embedding_api_calls`, `gigachat_calls`, `max_output_tokens`, `prompt_chars` и `usage_source`. Если GigaChat возвращает usage metadata, также выводятся `input_tokens`, `output_tokens` и `total_tokens`; иначе `estimated_input_tokens` является приблизительной оценкой. `embedding_input_tokens` и `embedding_total_tokens` выводятся отдельно, когда embeddings API предоставляет usage.

Для ограничения расходов используются настройки в `.env`: `GIGACHAT_MAX_TOKENS=450`, максимум два веб-источника, максимум три фрагмента Wiki.js, до 4200 символов отобранных фрагментов источника, последние четыре сообщения истории максимум по 600 символов. `MEMORY_SUMMARY_ENABLED=false` отключает периодические резюме истории, которые иначе могут вызвать дополнительный запрос модели.

Исторические версии v14–v17 использовали дополнительные проходы review/repair и более строгие правила, которые приводили к повторным ложным блокировкам. В v18–v19 они отключены в стандартном пути; вместо повторного вызова модели локально выполняются ограниченные проверки. Для поддерживаемого FAQ о мигрени используется краткий ответ, собранный из явно найденных фрагментов NICE. Это снижает расход токенов, но не гарантирует общую медицинскую правильность.
