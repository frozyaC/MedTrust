# MedTrust

Интеллектуальный справочник регистратора — система хранения, актуализации и семантического поиска по базе знаний медицинской клиники.

Фронтенд и бэкенд лежат в одном дереве. Интерфейс регистратора ходит в `POST /api/v1/query`.

## Проблема

- **Регистратор** тратит время на ручной поиск по ключевым словам; ответ не учитывает параметры пациента (пол, возраст, противопоказания).
- **Заведующий регистратурой** не видит пробелов в базе; устаревшие документы и коллизии не выявляются автоматически.
- **Пациент** ждёт дольше из-за сложных вопросов, требующих обращения к базе знаний.

## Решение

| Компонент | Описание |
|-----------|----------|
| **Семантический поиск** | Ответ на вопрос с учётом контекста пациента (возраст, пол, анамнез, противопоказания). Обратная связь от регистратора для оценки качества. |
| **Фиксация пробелов** | Вопросы без ответа автоматически передаются владельцу базы знаний. Опциональная генерация черновика статьи. |
| **Контроль коллизий** | При загрузке нового документа — проверка на противоречия с существующими статьями. |

## Целевая аудитория

Частные и государственные клиники с АРМ/CRM, структурированной базой знаний (wiki-формат), высоким потоком вопросов и широкой номенклатурой услуг.

## Frontend

Интерфейс регистратора находится в `frontend/`

## Запуск в Docker

1. Скопируйте `.env.withoutkeys` в `.env` и заполните `GIGACHAT_AUTH_DATA` и `EMBEDDING_API_KEY`.
2. Из корня репозитория:

```bash
docker compose up --build
```

- UI: `http://localhost:5173` (браузер ходит в API на `http://localhost:8000`)
- API / Swagger: `http://localhost:8000/docs`

3. Один раз проиндексируйте базу знаний:

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/reindex" \
  -F "file=@data/sample_sufler.zip"
```

Остановка: `docker compose down`. Том Postgres (`medtrust_pgdata`) при этом сохраняется.

## Backend

Path-aware RAG API. Поле `Путь:` из Wiki.js считается **частью смысла документа**, а не только технической ссылкой. Путь сохраняется как иерархия и участвует сразу в нескольких слоях поиска:

1. путь + заголовок + раздел + текст входят в текст для embeddings;
2. путь индексируется отдельным PostgreSQL `tsvector`;
3. итоговый hybrid retrieval объединяет dense, lexical и path retrieval через weighted RRF;
4. путь сохраняется в citation, чтобы frontend мог показать регистратору точное расположение статьи в Wiki.js.

### Архитектура

```text
ZIP/Markdown (Wiki.js export)
        |
        v
Document parser
  - Путь:
  - title
  - section hierarchy
        |
        v
Path-aware chunking
        |
        +--------------------------+
        |                          |
        v                          v
Qwen/Qwen3-Embedding-0.6B     PostgreSQL FTS
Cloud.ru OpenAI API          title/path/section/content
        |                          |
        +------------+-------------+
                     v
              PostgreSQL + pgvector
                     |
              weighted RRF
          dense + lexical + path
                     |
                  Top-K
                     |
                  GigaChat-2
                     |
          grounded answer + sources
```

### Что лежит в `data/`

`data/sample_sufler.zip` — исходный архив, предоставленный для MedTrust. В архиве 26 `.md`-статей. Файлы физически лежат в одном zip-каталоге, но логическая Wiki.js-иерархия задаётся строкой `Путь:` внутри каждого файла. Backend использует именно эту логическую структуру.

### Требования

- Python 3.11+
- Docker / Docker Compose
- GigaChat API credentials
- Cloud.ru Foundation Models API key

### Запуск

1. Внестите изменения в `.env` по примеру `.env.withoutkeys`.
2. Заполните `GIGACHAT_AUTH_DATA` и `EMBEDDING_API_KEY`.
3. Запустите PostgreSQL:

```bash
docker compose up -d db
```

4. Установите зависимости:

```bash
python -m venv .venv
.venv\\Scripts\\activate        # Windows
# source .venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
```

5. Запустите API:

```bash
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

### Индексация архива

Для проверки корректности работы лучше перейти в 
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/knowledge/reindex" \\
  -F "file=@data/sample_sufler.zip"
```

Ожидаемый результат: количество документов и chunks.

### Поиск без LLM

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/search" \\
  -H "Content-Type: application/json" \\
  -d '{"query":"Куда записать пациента при травме 5 дней назад?","top_k":5}'
```

В ответе будут отдельно видны `dense_rank`, `lexical_rank`, `path_rank` и итоговый `rrf_score`. Это удобно для отладки retrieval.

### RAG-вопрос

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/query" \\
  -H "Content-Type: application/json" \\
  -d '{
    "question":"Куда записать пациента при травме 5 дней назад?",
    "patient":{"age":35,"sex":"male","contraindications":[]},
    "top_k":5
  }'
```

### Endpoints

| Method | Endpoint | Назначение |
|---|---|---|
| GET | `/api/v1/health` | health-check |
| POST | `/api/v1/knowledge/reindex` | полная индексация ZIP с Markdown |
| POST | `/api/v1/search` | hybrid retrieval без LLM |
| POST | `/api/v1/query` | retrieval + GigaChat + citations |
| GET | `/api/v1/knowledge/{document_id}` | метаданные исходного документа |
| POST | `/api/v1/feedback` | обратная связь регистратора |

### Настройка path-aware retrieval

В `.env`:

```env
PATH_RRF_WEIGHT=1.25
DENSE_RRF_WEIGHT=1.00
LEXICAL_RRF_WEIGHT=1.00
```

По умолчанию путь немного усилен по сравнению с двумя остальными сигналами.

Индексируемый embedding text выглядит так:

```text
Путь: Регистратура > Словарь > Травмпункт > Травмпункт
Название: Травмпункт
Раздел: Травмпункт
Содержание:
...
```

Поэтому `Травмпункт`, `Лаборатория`, `Скрипты`, `Обзвон` и более глубокие разделы Wiki.js становятся частью retrieval semantics.

### Медицинские ограничения

Система не должна формировать медицинские рекомендации из собственных знаний модели. GigaChat получает только найденные фрагменты и должен сообщать об отсутствии достаточных подтверждений.

`patient` пока используется как retrieval/generation context. Отдельные фильтры по возрасту/полу/противопоказаниям можно добавить, когда в Wiki.js появятся явные структурированные metadata для таких ограничений.
