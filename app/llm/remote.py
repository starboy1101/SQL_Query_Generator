from __future__ import annotations

import logging

import httpx2

from app.core.errors import ModelUnavailableError
from app.llm.base import GenerationInput

logger = logging.getLogger(__name__)


class OpenAICompatibleBackend:
    """Remote inference through a vLLM/TGI-style OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: float,
        max_new_tokens: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_new_tokens = max_new_tokens

    @property
    def model_id(self) -> str:
        return self._model

    def warmup(self) -> None:
        return None

    def generate(self, generation_input: GenerationInput) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": generation_input.prompt}],
            "temperature": 0,
            "max_tokens": self._max_new_tokens,
        }
        try:
            with httpx2.Client(timeout=self._timeout) as client:
                response = client.post(f"{self._base_url}/v1/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            return str(data["choices"][0]["message"]["content"])
        except (httpx2.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Remote model request failed", extra={"error_type": type(exc).__name__})
            raise ModelUnavailableError("The remote language-model endpoint is unavailable") from exc
