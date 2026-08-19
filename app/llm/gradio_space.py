from __future__ import annotations

import logging
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import suppress
from typing import Any

from gradio_client import Client

from app.core.errors import ModelUnavailableError
from app.llm.base import GenerationInput

logger = logging.getLogger(__name__)

MAX_SPACE_RESPONSE_CHARS = 20_000
INVALID_DECODE_MARKERS = ("Ċ", "Ġ")


class GradioSpaceBackend:
    """Inference through a named Gradio API hosted on Hugging Face Spaces."""

    def __init__(
        self,
        *,
        space_id: str,
        token: str | None,
        api_name: str,
        model: str,
        timeout: float,
        max_new_tokens: int,
    ) -> None:
        normalized_space_id = space_id.strip()
        if not normalized_space_id:
            raise ValueError("HF_SPACE_ID is required for LLM_BACKEND=huggingface_space")

        normalized_api_name = api_name.strip()
        if not normalized_api_name:
            raise ValueError("HF_SPACE_API_NAME cannot be empty")

        self._space_id = normalized_space_id
        self._token = token
        self._api_name = (
            normalized_api_name
            if normalized_api_name.startswith("/")
            else f"/{normalized_api_name}"
        )
        self._model = model
        self._timeout = timeout
        self._max_new_tokens = max_new_tokens
        self._client: Client | None = None
        self._client_lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return self._model

    def warmup(self) -> None:
        self._get_client()

    def generate(self, generation_input: GenerationInput) -> str:
        job: Any = None
        try:
            job = self._get_client().submit(
                prompt=generation_input.prompt,
                max_new_tokens=self._max_new_tokens,
                api_name=self._api_name,
            )
            result = job.result(timeout=self._timeout)
            return self._validate_result(result)
        except FutureTimeoutError as exc:
            if job is not None:
                with suppress(Exception):
                    job.cancel()
            logger.warning(
                "Hugging Face Space request timed out",
                extra={"space_id": self._space_id},
            )
            raise ModelUnavailableError("The Hugging Face Space timed out") from exc
        except ModelUnavailableError:
            raise
        except Exception as exc:
            logger.warning(
                "Hugging Face Space request failed",
                extra={
                    "space_id": self._space_id,
                    "error_type": type(exc).__name__,
                },
            )
            raise ModelUnavailableError("The Hugging Face Space is unavailable") from exc

    @staticmethod
    def _validate_result(result: object) -> str:
        if not isinstance(result, str):
            raise ModelUnavailableError("The Hugging Face Space returned an invalid response")

        normalized = result.strip()
        if not normalized:
            raise ModelUnavailableError("The Hugging Face Space returned an empty response")
        if len(normalized) > MAX_SPACE_RESPONSE_CHARS:
            raise ModelUnavailableError("The Hugging Face Space response was too large")
        if "\x00" in normalized or any(marker in normalized for marker in INVALID_DECODE_MARKERS):
            raise ModelUnavailableError("The Hugging Face Space returned malformed text")
        return normalized

    def _get_client(self) -> Client:
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is None:
                self._client = Client(
                    self._space_id,
                    token=self._token,
                    max_workers=4,
                    verbose=False,
                    httpx_kwargs={"timeout": self._timeout},
                    download_files=False,
                    analytics_enabled=False,
                )
        return self._client
