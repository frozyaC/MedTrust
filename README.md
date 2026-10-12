# MedTrust — Path-Aware Hybrid RAG Backend

MVP backend для интеллектуального справочника регистратора. В проекте реализованы path-aware ingestion из Wiki.js Markdown, Qwen embeddings, PostgreSQL/pgvector + FTS, weighted RRF, GigaChat, долгосрочная память диалога и web-search fallback. Тематический scope guard на входе запроса отключён: запрос не блокируется по словарю ключевых слов.

## Архитектура

```text
Frontend chat
     |
     v
POST /api/v1/query
     |
     +--> conversation_id -> PostgreSQL memory
     +--> contextualize follow-up
     +--> Qwen Embedding -> dense search
     +--> PostgreSQL FTS + path retrieval
     |               |
     |               v
     |           weighted RRF
     |               |
     |               v
     |       ranked Wiki candidates ---------+
     |          |                  |         |
     |     strong match       weak/no match  |
     |          |                  |         |
     |          |              SearXNG web  |
     |          |                  |         |
     +----------+------------------+---------+
                        |
                        v
               GigaChat answer generation
        (also runs when no sources were found)
                        |
                        v
    answer + source candidates + retrieval diagnostics
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

Если поисковые движки возвращают безопасные, но не относящиеся к вопросу страницы, они отбрасываются и `web_search_status` отражает отсутствие релевантных результатов. Это не блокирует генерацию: модель всё равно отвечает из общих знаний, когда может, и явно отмечает, что подтверждения в найденных материалах нет. Если SearXNG недоступен или источники не найдены, сервис не выдумывает ссылки и не утверждает, что ответ подтверждён Wiki.

В `sources` возвращаются найденные кандидаты; поле `used_in_answer` показывает, есть ли соответствующая метка (`[W1]`, `[WEB1]` и т. п.) в ответе. Источник может быть полезен как контекст даже при низком similarity score, но такие score сами по себе не подтверждают корректность ответа.

Подробнее: `docs/WEB_SEARCH.md`.


## Поиск и генерация ответов (v22)

На входе нет тематического scope guard: вопросы не блокируются из-за отсутствия слова из фиксированного медицинского словаря. `/api/v1/search` и `/api/v1/query` сначала выполняют retrieval. Это важно для вопросов обычным языком вроде «Как подготовиться к гастроскопии?», где термин запроса может не совпадать со словами в названии Wiki-статьи.

Гибридный поиск ранжирует фрагменты через dense, lexical и path retrieval с weighted RRF. Порог `web_min_wiki_dense_similarity` помогает решить, стоит ли дополнительно обращаться к SearXNG, но больше не запрещает передавать слабые Wiki-кандидаты в контекст модели. Если надёжного Wiki-совпадения нет, web-search выполняется как fallback, а лучшими найденными Wiki-фрагментами всё равно можно дополнить контекст. Allowlist HTTPS-доменов и тематическая фильтрация web-результатов остаются отдельной защитой качества внешних источников.

После генерации ответ не заменяется сообщением «Данных может быть недостаточно» только потому, что модель не поставила цитату, использовала неизвестную метку или не выполнила фиксированный чек-лист. Если релевантные источники не найдены, GigaChat всё равно получает запрос и может дать справочный ответ из общих знаний; модель должна явно обозначить отсутствие подтверждения в базе MedTrust и не выдумывать источники. Для медицинских вопросов ответ остаётся справочным и не должен подменять индивидуальную консультацию.

В API `answer_validation_mode=non_blocking_diagnostics_only`: метки источников отслеживаются для диагностики и никогда не служат блокирующим условием ответа. `answer_reviewed` и `source_checks_passed` отражают только наблюдавшееся соответствие цитат найденным источникам, а не клиническую проверку. `sources` содержит кандидатов, переданных модели, с флагом `used_in_answer`; `retrieval` показывает ранги и score. `eligible_for_answer=true` означает, что фрагмент попал в выбранный контекст, а не то, что его медицинская корректность автоматически подтверждена.

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

## История изменений

В v20 исправлялось дублирование разделов в компактном NICE-шаблоне. В v21 отключили блокирующий медицинский чек-лист. В v22 дополнительно отключён тематический scope guard, порог similarity перестал исключать Wiki-фрагменты из контекста, а отсутствие источников или цитат больше не блокирует генерацию ответа.

### Полный текст клинических рекомендаций NICE

Когда SearXNG возвращает обзор NICE вместо содержательного раздела, MedTrust автоматически получает страницу `/guidance/<id>/chapter/recommendations` для запросов о диагностике, лечении, симптомах или рекомендациях. Парсер отдаёт RAG основной текст страницы, а не только обзорный сниппет; ссылки в `sources` ведут на фактически использованный раздел. Для вопроса о диагностике мигрени у взрослых при наличии полного набора разделов используется краткий шаблон без вызова GigaChat; если доступен лишь короткий фрагмент таблицы, ответ ограничивается подтверждёнными признаками боли и явно предупреждает, что полного текста недостаточно.


### Диагностика и контроль расходов

`POST /api/v1/query` возвращает `answer_review_diagnostics`, `answer_validation_mode`, `source_checks_passed` и `resource_usage`. В `non_blocking_diagnostics_only` нет проверки, которая могла бы заменить готовый ответ. Отбор и allowlist web-источников применяются до передачи их в prompt, но не используются как глобальный запрет на генерацию.

Обычный запрос без детерминированного FAQ-шаблона выполняет максимум один вызов GigaChat, включая случаи, когда Wiki и web не вернули пригодных источников. Шаблон на основе полного текста NICE может вернуть ответ с `gigachat_calls=0`. `resource_usage` показывает фактические вызовы и токены, когда провайдер возвращает usage metadata; параметры `GIGACHAT_MAX_TOKENS`, `RAG_MAX_WEB_SOURCES`, `RAG_MAX_WIKI_SOURCES`, `RAG_MAX_SOURCE_CHARS`, `RAG_MAX_HISTORY_MESSAGES` и `MEMORY_SUMMARY_ENABLED` продолжают ограничивать расходы.

Целевые precision, recall и accuracy выше 0.95 пока не подтверждены: их нужно измерить на размеченном наборе запросов с независимой оценкой источников и фактических утверждений.
