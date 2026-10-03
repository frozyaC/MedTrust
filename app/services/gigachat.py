import threading
import time
import uuid
from functools import lru_cache

import requests

from app.core.config import get_settings


class GigaChatClient:
    """OAuth -> Bearer -> chat/completions REST flow."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at:
            return self._token

        with self._lock:
            now = time.time()
            if self._token and now < self._expires_at:
                return self._token
            response = requests.post(
                self.settings.gigachat_auth_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "RqUID": str(uuid.uuid4()),
                    "Authorization": f"Basic {self.settings.gigachat_auth_data}",
                },
                data={"scope": self.settings.gigachat_scope},
                timeout=20,
                verify=self.settings.gigachat_verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._expires_at = float(payload.get("expires_at", now + 1800)) - self.settings.gigachat_token_safety_seconds
            return self._token

    def chat_messages(self, messages: list[dict[str, str]]) -> str:
        token = self.get_access_token()
        url = f"{self.settings.gigachat_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
        }
        body = {
            "model": self.settings.gigachat_model,
            "messages": messages,
            "temperature": 0.1,
        }
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=40,
            verify=self.settings.gigachat_verify_ssl,
        )
        if response.status_code == 401:
            self._token = None
            headers["Authorization"] = f"Bearer {self.get_access_token()}"
            response = requests.post(
                url, headers=headers, json=body, timeout=40,
                verify=self.settings.gigachat_verify_ssl,
            )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def chat(self, prompt: str) -> str:
        return self.chat_messages([
            {
                "role": "system",
                "content": (
                    "Ты — ассистент регистратора медицинской клиники. "
                    "Отвечай только на основании предоставленных источников и контекста диалога. "
                    "Не придумывай медицинские факты. Строка 'нужные данные не найдены' "
                    "используется только когда предоставленные источники вообще не содержат "
                    "достаточно данных для полезного ответа. Если хотя бы один источник прямо "
                    "отвечает на вопрос, дай ответ на его основании и не отказывайся только потому, "
                    "что источник является кратким фрагментом. Каждый существенный тезис сопровождай "
                    "[W1], [WEB1] и т. п."
                ),
            },
            {"role": "user", "content": prompt},
        ])


@lru_cache(maxsize=1)
def get_gigachat_client() -> GigaChatClient:
    return GigaChatClient()
