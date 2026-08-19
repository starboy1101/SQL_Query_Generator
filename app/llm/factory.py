from __future__ import annotations

from app.core.config import Settings
from app.db.schema import SchemaIntrospector
from app.llm.base import LLMBackend
from app.llm.gradio_space import GradioSpaceBackend
from app.llm.heuristic import HeuristicBackend
from app.llm.huggingface import HuggingFaceBackend
from app.llm.remote import OpenAICompatibleBackend


def create_llm_backend(settings: Settings, introspector: SchemaIntrospector) -> LLMBackend:
    if settings.llm_backend == "heuristic":
        return HeuristicBackend(introspector.get_schema)
    if settings.llm_backend == "huggingface":
        return HuggingFaceBackend(
            model_name_or_path=settings.model_name_or_path,
            adapter_path=settings.adapter_path,
            device=settings.model_device,
            use_4bit=settings.model_use_4bit,
            trust_remote_code=settings.model_trust_remote_code,
            max_input_tokens=settings.model_max_input_tokens,
            max_new_tokens=settings.model_max_new_tokens,
            temperature=settings.model_temperature,
        )
    if settings.llm_backend == "huggingface_space":
        return GradioSpaceBackend(
            space_id=settings.hf_space_id,
            token=settings.hf_space_token,
            api_name=settings.hf_space_api_name,
            model=settings.model_name_or_path,
            timeout=settings.model_request_timeout_seconds,
            max_new_tokens=settings.model_max_new_tokens,
        )
    return OpenAICompatibleBackend(
        base_url=settings.model_api_base_url,
        api_key=settings.model_api_key,
        model=settings.model_name_or_path,
        timeout=settings.model_request_timeout_seconds,
        max_new_tokens=settings.model_max_new_tokens,
    )
