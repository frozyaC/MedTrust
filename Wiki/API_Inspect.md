# Проверка доступных API MedTrust

## 1. Запуск

Из корня проекта:

```powershell
docker compose up -d db searxng api frontend
```

После запуска API доступен по адресу `http://localhost:8000`.

## 2. Swagger и OpenAPI

Интерактивная документация:

```text
http://localhost:8000/docs
```

Альтернативная документация:

```text
http://localhost:8000/redoc
```

Исходный контракт OpenAPI:

```text
http://localhost:8000/openapi.json
```

В Swagger можно раскрыть endpoint, нажать `Try it out`, заполнить JSON и посмотреть фактический HTTP-ответ.

Получить OpenAPI из PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/openapi.json |
    ConvertTo-Json -Depth 20
```

OpenAPI можно импортировать в Postman, Insomnia или Swagger Editor.

## 3. Доступные endpoint'ы

Все маршруты API имеют префикс `/api/v1`.

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Проверка API и базы данных |
| `POST` | `/api/v1/query` | RAG-запрос и генерация ответа |
| `POST` | `/api/v1/search` | Поиск по базе знаний |
| `POST` | `/api/v1/knowledge/reindex` | Переиндексация ZIP-архива с Markdown |
| `GET` | `/api/v1/knowledge/{document_id}` | Получение документа |
| `POST` | `/api/v1/conversations` | Создание диалога |
| `GET` | `/api/v1/conversations` | Список диалогов |
| `GET` | `/api/v1/conversations/{conversation_id}` | Диалог с сообщениями |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | Сообщения диалога |
| `POST` | `/api/v1/feedback` | Сохранение оценки ответа |

Источники маршрутов: `app/api/routes.py` и `app/main.py`.

## 4. Проверка основных запросов

Проверка состояния:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

Поиск:

```powershell
$body = @{
    query = "Куда записать пациента?"
    top_k = 5
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://localhost:8000/api/v1/search `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

RAG-запрос:

```powershell
$body = @{
    question = "Куда записать пациента?"
    patient = $null
    top_k = 5
    conversation_id = $null
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri http://localhost:8000/api/v1/query `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

Проверка web-search напрямую:

```powershell
Invoke-RestMethod "http://localhost:8080/search?q=мигрень&format=json"
```

## 5. Где смотреть схемы сообщений

Входные модели описаны в `app/schemas/api.py`:

- `QueryRequest`;
- `SearchRequest`;
- `PatientContext`;
- `CreateConversationRequest`;
- `FeedbackRequest`.

Они автоматически попадают в OpenAPI и отображаются в Swagger.

Ответы некоторых маршрутов сейчас возвращаются как обычный `dict`. Поэтому OpenAPI может не показывать их детальную структуру. Для полного контракта ответа следует создать Pydantic-модель и указать ее в `response_model`:

```python
@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    ...
```

После этого схема ответа появится в разделе `Responses` Swagger.

## 6. Как посмотреть взаимодействие компонентов

Логи контейнеров:

```powershell
docker compose logs -f api
docker compose logs -f searxng
docker compose logs -f db
```

Инфраструктурные границы описаны в `docker-compose.yml`:

- `frontend` — пользовательский интерфейс;
- `api` — FastAPI и RAG-оркестрация;
- `db` — PostgreSQL/pgvector;
- `searxng` — web-search provider.

Для полного пути одного запроса рекомендуется подключить OpenTelemetry и Jaeger или Grafana Tempo. Тогда можно увидеть отдельные операции: загрузку истории, embeddings, поиск в PostgreSQL, обращение к SearXNG и вызов GigaChat.

## 7. Быстрая проверка доступности

```powershell
$urls = @(
    "http://localhost:8000/api/v1/health",
    "http://localhost:8000/openapi.json",
    "http://localhost:8080/search?q=test&format=json"
)

foreach ($url in $urls) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing
        "$($response.StatusCode) $url"
    } catch {
        "ERROR ${url}: $($_.Exception.Message)"
    }
}
```
