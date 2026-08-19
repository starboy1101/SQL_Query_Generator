from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError

import httpx2
import pytest

from app.core.config import Settings
from app.core.errors import ModelUnavailableError
from app.db.schema import SchemaIntrospector
from app.llm.base import GenerationInput
from app.llm.factory import create_llm_backend
from app.llm.gradio_space import GradioSpaceBackend
from app.llm.huggingface import HuggingFaceBackend
from app.llm.remote import OpenAICompatibleBackend


def generation_input() -> GenerationInput:
    return GenerationInput(prompt="prompt", question="question", dialect="sqlite", max_rows=10)


def test_factory_creates_remote_backend(database_path: object) -> None:
    from app.db.gateway import create_database_engine

    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        llm_backend="openai_compatible",
        model_name_or_path="test-model",
    )
    engine = create_database_engine(settings.database_url)
    try:
        backend = create_llm_backend(settings, SchemaIntrospector(engine, dialect="sqlite"))
    finally:
        engine.dispose()
    assert isinstance(backend, OpenAICompatibleBackend)
    assert backend.model_id == "test-model"
    assert backend.warmup() is None


def test_remote_backend_parses_chat_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "SELECT 1"}}]}

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 5

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
            assert url.endswith("/v1/chat/completions")
            assert headers["Authorization"] == "Bearer token"
            assert json["model"] == "model"
            return FakeResponse()

    monkeypatch.setattr("app.llm.remote.httpx2.Client", FakeClient)
    backend = OpenAICompatibleBackend(
        base_url="http://model",
        api_key="token",
        model="model",
        timeout=5,
        max_new_tokens=256,
    )
    assert backend.generate(generation_input()) == "SELECT 1"


def test_remote_backend_maps_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingClient:
        def __init__(self, *, timeout: float) -> None:
            pass

        def __enter__(self) -> FailingClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, *args: object, **kwargs: object) -> object:
            raise httpx2.ConnectError("offline")

    monkeypatch.setattr("app.llm.remote.httpx2.Client", FailingClient)
    backend = OpenAICompatibleBackend(
        base_url="http://model",
        api_key=None,
        model="model",
        timeout=5,
        max_new_tokens=256,
    )
    with pytest.raises(ModelUnavailableError):
        backend.generate(generation_input())


def test_huggingface_backend_reports_adapter_as_model_id() -> None:
    backend = HuggingFaceBackend(
        model_name_or_path="base",
        adapter_path="adapter",
        device="auto",
        use_4bit=False,
        trust_remote_code=False,
        max_input_tokens=100,
        max_new_tokens=20,
        temperature=0,
    )
    assert backend.model_id == "adapter"


def test_factory_creates_hugging_face_space_backend(database_path: object) -> None:
    from app.db.gateway import create_database_engine

    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        llm_backend="huggingface_space",
        hf_space_id="owner/sql-space",
        model_name_or_path="prem-research/prem-1B-SQL",
    )
    engine = create_database_engine(settings.database_url)
    try:
        backend = create_llm_backend(settings, SchemaIntrospector(engine, dialect="sqlite"))
    finally:
        engine.dispose()

    assert isinstance(backend, GradioSpaceBackend)
    assert backend.model_id == "prem-research/prem-1B-SQL"


def test_hugging_face_space_backend_submits_named_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeJob:
        def result(self, *, timeout: float) -> str:
            calls["result_timeout"] = timeout
            return "  SELECT COUNT(*) FROM customers;  "

    class FakeClient:
        def __init__(self, src: str, **kwargs: object) -> None:
            calls["src"] = src
            calls["client_kwargs"] = kwargs

        def submit(self, **kwargs: object) -> FakeJob:
            calls["submit_kwargs"] = kwargs
            return FakeJob()

    monkeypatch.setattr("app.llm.gradio_space.Client", FakeClient)
    backend = GradioSpaceBackend(
        space_id=" owner/sql-space ",
        token="secret",
        api_name="generate",
        model="prem-model",
        timeout=5,
        max_new_tokens=128,
    )

    assert backend.generate(generation_input()) == "SELECT COUNT(*) FROM customers;"
    assert calls["src"] == "owner/sql-space"
    assert calls["result_timeout"] == 5
    assert calls["submit_kwargs"] == {
        "prompt": "prompt",
        "max_new_tokens": 128,
        "api_name": "/generate",
    }
    client_kwargs = calls["client_kwargs"]
    assert isinstance(client_kwargs, dict)
    assert client_kwargs["token"] == "secret"
    assert client_kwargs["httpx_kwargs"] == {"timeout": 5}
    assert backend.warmup() is None


def test_hugging_face_space_backend_cancels_timed_out_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = False

    class FakeJob:
        def result(self, *, timeout: float) -> str:
            raise FutureTimeoutError

        def cancel(self) -> None:
            nonlocal cancelled
            cancelled = True

    class FakeClient:
        def __init__(self, src: str, **kwargs: object) -> None:
            pass

        def submit(self, **kwargs: object) -> FakeJob:
            return FakeJob()

    monkeypatch.setattr("app.llm.gradio_space.Client", FakeClient)
    backend = GradioSpaceBackend(
        space_id="owner/sql-space",
        token=None,
        api_name="/generate",
        model="prem-model",
        timeout=5,
        max_new_tokens=128,
    )

    with pytest.raises(ModelUnavailableError, match="timed out"):
        backend.generate(generation_input())
    assert cancelled


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"sql": "SELECT 1"},
        "",
        "   ",
        "SELECT 1\x00",
        "SELECT 1Ċ",
        "SELECT 1ĠFROM customers",
        "SELECT 1" + ("x" * 20_000),
    ],
)
def test_hugging_face_space_backend_rejects_malformed_responses(
    monkeypatch: pytest.MonkeyPatch,
    result: object,
) -> None:
    class FakeJob:
        def result(self, *, timeout: float) -> object:
            return result

    class FakeClient:
        def __init__(self, src: str, **kwargs: object) -> None:
            pass

        def submit(self, **kwargs: object) -> FakeJob:
            return FakeJob()

    monkeypatch.setattr("app.llm.gradio_space.Client", FakeClient)
    backend = GradioSpaceBackend(
        space_id="owner/sql-space",
        token=None,
        api_name="/generate",
        model="prem-model",
        timeout=5,
        max_new_tokens=128,
    )

    with pytest.raises(ModelUnavailableError):
        backend.generate(generation_input())


def test_hugging_face_space_backend_requires_configuration() -> None:
    with pytest.raises(ValueError, match="HF_SPACE_ID"):
        GradioSpaceBackend(
            space_id=" ",
            token=None,
            api_name="/generate",
            model="prem-model",
            timeout=5,
            max_new_tokens=128,
        )
