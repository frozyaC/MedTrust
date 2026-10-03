# Web-search fallback через SearXNG

MedTrust использует локальный экземпляр SearXNG как web-search provider. SearXNG предоставляет HTTP API, в котором можно запросить результаты в формате JSON через `GET /search?q=...&format=json`; формат `json` должен быть включён в `search.formats` в `settings.yml`.

## Архитектура

```text
POST /api/v1/query
        |
        v
   scope validation
        |
        v
 Wiki.js hybrid retrieval
        |
        +---- достаточно релевантно ----> GigaChat
        |
        +---- недостаточно ------------> SearXNG
                                          |
                                          v
                                    WEB1 / WEB2 / WEB3
                                          |
                                          v
                                       GigaChat
```

SearXNG запускается локально в Docker. Официальная документация поддерживает container/Compose-развёртывание и конфигурацию через `/etc/searxng/settings.yml`.

## Конфигурация

В `.env` достаточно указать:

```env
WEB_SEARCH_ENABLED=true
SEARXNG_URL=http://127.0.0.1:8080
WEB_SEARCH_TIMEOUT_SECONDS=15
WEB_SEARCH_FALLBACK_TIMEOUT_SECONDS=8
WEB_SEARCH_LANGUAGE=ru
WEB_FALLBACK_MAX_DOMAINS=4
WEB_FALLBACK_DOMAINS=nice.org.uk,pubmed.ncbi.nlm.nih.gov,cr.minzdrav.gov.ru,who.int
WEB_SOURCE_MAX_CHARS=6000
WEB_MIN_WIKI_DENSE_SIMILARITY=0.62
```

API key для MedTrust не нужен.

## Запуск

```powershell
docker compose up -d db searxng
```

Проверка UI:

```text
http://127.0.0.1:8080
```

Проверка JSON API:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/search?q=мигрень&format=json"
```

## Безопасность web-источников

Внешний ответ сначала проходит allowlist:

1. Сначала проверяется обычный поиск.
2. URL должен использовать `https`.
3. Домен должен точно совпадать с `WEB_SAFE_DOMAINS` или быть его поддоменом.
4. Если безопасных результатов недостаточно, выполняются доменные запросы `site:<domain> <query>` для доменов из `WEB_FALLBACK_DOMAINS`.
5. После объединения и фильтрации используются максимум три результата; первый fallback-проход старается дать результаты с разных авторитетных доменов.
6. Для safe URL выполняется попытка получить полный HTML; из него извлекается обычный текст размером до `WEB_SOURCE_MAX_CHARS`. Если страница недоступна, сохраняется исходный snippet SearXNG. При обогащении HTTP-редиректы не следуются.
7. В prompt каждый результат маркируется `[WEB1]`, `[WEB2]`, `[WEB3]`.
8. Web-контент считается недоверенным: GigaChat получает явную инструкцию игнорировать любые инструкции внутри найденных страниц.
9. Structured `patient` context не отправляется в SearXNG.

Allowlist находится в `.env` и позволяет ограничить ответы медицинскими источниками.

## Доменный fallback

Например, для запроса о диагностике мигрени backend может дополнительно отправить в SearXNG запросы вида:

```text
site:nice.org.uk Какие современные рекомендации по диагностике мигрени у взрослых?
site:pubmed.ncbi.nlm.nih.gov Какие современные рекомендации по диагностике мигрени у взрослых?
site:cr.minzdrav.gov.ru Какие современные рекомендации по диагностике мигрени у взрослых?
site:who.int Какие современные рекомендации по диагностике мигрени у взрослых?
```

Это позволяет использовать результаты NICE, PubMed, клинических рекомендаций Минздрава и WHO даже в ситуации, когда обычный поиск в первую очередь возвращает Wikipedia или коммерческие сайты. Эти страницы всё равно проходят тот же HTTPS + allowlist фильтр.

## Статусы

`SearXNGWebSearchClient` возвращает:

- `not_attempted` — поиск не запускался;
- `success` — найдены и прошли allowlist результаты;
- `disabled` — web-search выключен;
- `no_provider_results` — SearXNG не вернул результатов;
- `no_safe_results` — результаты были, но не прошли allowlist;
- `api_error` — ошибка HTTP/сети;
- `invalid_response` — ответ не удалось разобрать как JSON.

Если Wiki.js недостаточно релевантен и ни обычный, ни доменный SearXNG-поиск не дают безопасных результатов, `/api/v1/query` возвращает ровно `нужные данные не найдены`.

## Answerability и prompt

Если Wiki.js не проходит answerability gate, нерелевантные Wiki-фрагменты не передаются в prompt как доказательства. GigaChat получает safe web-источники, может синтезировать ответ из нескольких источников и должен использовать `нужные данные не найдены` только тогда, когда источники вообще не содержат достаточно информации.

## Контроль целостности цитат

При fallback на SearXNG нерелевантные Wiki.js результаты исключаются из evidence set. Для web-only ответа разрешены только метки `WEB1`, `WEB2`, `WEB3`. Backend проверяет цитаты ответа и не принимает ссылку на источник, который не был реально передан модели.
