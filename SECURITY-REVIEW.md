# MedTrust Security Review

Дата проверки: 2026-11-09

## Область проверки

Проверены доступность backend API из внешней сети, защита вызовов GigaChat, frontend-аутентификация, CORS и TLS-настройки.

## Findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | HIGH | `app/api/routes.py`, `app/main.py` | `routes.py:23-72`, `main.py:18-26` | Backend-маршруты подключены без серверной аутентификации. Внешний пользователь может вызвать `/api/v1/query`, который косвенно использует GigaChat, а также `/api/v1/web-search` и `/api/v1/search`. API публикуется через Docker на порту 8000. | 10/10 |
| 2 | HIGH | `app/api/routes.py` | `41-176` | Без авторизации доступны переиндексация БЗ, чтение диалогов и документов, а также просмотр и изменение карты пробелов. | 10/10 |
| 3 | HIGH | `frontend/src/App.tsx`, `frontend/src/main.tsx` | `App.tsx:313-316`, `main.tsx:8-13` | Frontend-аутентификация не является механизмом защиты: принимаются любые непустые учетные данные, а флаг в `localStorage` можно установить вручную. | 10/10 |
| 4 | HIGH | `app/core/config.py`, `app/services/gigachat.py` | `config.py:14`, `gigachat.py:93,121,128` | TLS-проверка соединений с GigaChat по умолчанию отключена (`gigachat_verify_ssl=False`), что создает риск перехвата credentials или bearer-токена при атаке посредника. | 9/10 |

## Вывод

Прямого маршрута `/gigachat` или `/chat/completions` в backend нет. Однако без серверной аутентификации внешний пользователь может использовать GigaChat косвенно через `POST /api/v1/query`.

CORS не защищает API от прямых HTTP-запросов. Если порт backend доступен из внешней сети, любой клиент может обращаться к API независимо от frontend.

## Рекомендации

1. Добавить backend-аутентификацию и проверку сессии/JWT на каждом защищенном маршруте.
2. Ограничить `/api/v1/query`, `/api/v1/search` и `/api/v1/web-search` авторизованными пользователями и добавить rate limit/квоты.
3. Ограничить `/api/v1/knowledge/reindex` и `/api/v1/knowledge-gaps/*` ролью владельца БЗ/администратора.
4. Проверять владельца `conversation_id` при чтении диалогов и сообщений.
5. Не доверять `localStorage` для контроля доступа.
6. Не передавать GigaChat credentials во frontend и не вызывать GigaChat напрямую из браузера.
7. В production включить TLS certificate verification и использовать `gigachat_verify_ssl=True`.
8. Ограничить публикацию backend-порта reverse proxy, VPN или сетевым firewall, если API не должен быть доступен из интернета.

## Приоритет

До публичного хостинга необходимо закрыть пункты 1-3. Пункт 4 также следует исправить до production-эксплуатации, особенно если соединение с GigaChat проходит через недоверенные сети.
