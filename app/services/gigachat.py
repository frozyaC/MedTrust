import threading
import time
import uuid

import requests

from app.core.config import get_settings


class GigaChatClient:
    """REST client that follows the OAuth -> Bearer -> chat/completions flow."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._token: str | None = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    def get_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at:
            return self._token

        with self._lock:
            now = time.time()
            if self._token and now < self._expires_at:
                return self._token

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self.settings.gigachat_auth_data}",
            }
            response = requests.post(
                self.settings.gigachat_auth_url,
                headers=headers,
                data={"scope": self.settings.gigachat_scope},
                timeout=20,
                verify=self.settings.gigachat_verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()

            self._token = payload["access_token"]
            expires_at = float(payload.get("expires_at", now + 1800))
            self._expires_at = expires_at - self.settings.gigachat_token_safety_seconds
            return self._token

    def chat(self, prompt: str) -> str:
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
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ты — ассистент регистратора медицинской клиники. "
                        "Отвечай только на основании переданного контекста базы знаний. "
                        "Не добавляй сведения из собственных знаний. "
                        "Если подтверждения нет или источники конфликтуют, прямо укажи это. "
                        "Для каждого существенного утверждения указывай [Источник N]."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=40,
            verify=self.settings.gigachat_verify_ssl,
        )

        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
