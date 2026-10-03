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
5. после объединения и allowlist выбираются максимум три результата: `WEB1`, `WEB2`, `WEB3`;
6. для каждого safe URL backend пытается получить полный HTML и передать GigaChat расширенный текст страницы; при ошибке остаётся поисковый snippet; HTTP-редиректы не следуются при обогащении источника.

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

При доступном SearXNG и наличии безопасных результатов (в том числе найденных через доменный fallback) признаки работающего fallback:

```json
"web_search_attempted": true,
"web_search_used": true,
"web_search_status": "success"
```

В `sources` должны появиться использованные моделью веб-источники `[WEB1]`, `[WEB2]` и т. п. Если SearXNG недоступен, результаты не проходят allowlist или сами поисковые движки не возвращают подходящих страниц, backend не подменяет это выдуманным ответом и возвращает `нужные данные не найдены`.

Подробнее: `docs/WEB_SEARCH.md`.

## Sources

`/api/v1/query` возвращает `sources` только для источников, чьи citation markers (`[W1]`, `[WEB1]`) реально присутствуют в ответе модели. Если Wiki.js не прошёл answerability gate, нерелевантные Wiki-фрагменты не передаются GigaChat как доказательство: в prompt остаются только safe web-источники.

`retrieval` — отдельный отладочный массив с `dense_rank`, `lexical_rank`, `path_rank`, `dense_similarity` и `rrf_score`.

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
