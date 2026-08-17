from __future__ import annotations

import logging
import threading
from typing import Any

from app.core.errors import ModelUnavailableError
from app.llm.base import GenerationInput

logger = logging.getLogger(__name__)


class HuggingFaceBackend:
    """Lazy local inference for a base CodeLlama model plus an optional PEFT adapter."""

    def __init__(
        self,
        *,
        model_name_or_path: str,
        adapter_path: str | None,
        device: str,
        use_4bit: bool,
        trust_remote_code: bool,
        max_input_tokens: int,
        max_new_tokens: int,
        temperature: float,
    ) -> None:
        self._model_name = model_name_or_path
        self._adapter_path = adapter_path
        self._device = device
        self._use_4bit = use_4bit
        self._trust_remote_code = trust_remote_code
        self._max_input_tokens = max_input_tokens
        self._max_new_tokens = max_new_tokens
        self._temperature = temperature
        self._model: Any = None
        self._tokenizer: Any = None
        self._lock = threading.Lock()

    @property
    def model_id(self) -> str:
        return self._adapter_path or self._model_name

    def warmup(self) -> None:
        self._ensure_loaded()

    def generate(self, generation_input: GenerationInput) -> str:
        self._ensure_loaded()
        import torch

        formatted_prompt = f"<s>[INST] {generation_input.prompt.strip()} [/INST]"
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self._max_input_tokens,
        )
        model_device = next(self._model.parameters()).device
        inputs = {key: value.to(model_device) for key, value in inputs.items()}
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": self._max_new_tokens,
            "pad_token_id": self._tokenizer.eos_token_id,
            "eos_token_id": self._tokenizer.eos_token_id,
            "do_sample": self._temperature > 0,
        }
        if self._temperature > 0:
            generation_kwargs["temperature"] = self._temperature

        with torch.inference_mode():
            output = self._model.generate(**inputs, **generation_kwargs)
        generated_tokens = output[0][inputs["input_ids"].shape[1] :]
        return str(self._tokenizer.decode(generated_tokens, skip_special_tokens=True)).strip()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

                quantization_config = None
                if self._use_4bit:
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=torch.bfloat16
                        if torch.cuda.is_bf16_supported()
                        else torch.float16,
                        bnb_4bit_use_double_quant=True,
                    )
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model_name,
                    trust_remote_code=self._trust_remote_code,
                )
                if self._tokenizer.pad_token_id is None:
                    self._tokenizer.pad_token = self._tokenizer.eos_token
                self._model = AutoModelForCausalLM.from_pretrained(
                    self._model_name,
                    device_map=self._device,
                    quantization_config=quantization_config,
                    torch_dtype="auto",
                    trust_remote_code=self._trust_remote_code,
                )
                if self._adapter_path:
                    from peft import PeftModel

                    self._model = PeftModel.from_pretrained(self._model, self._adapter_path)
                self._model.eval()
                logger.info("Local language model loaded", extra={"model_id": self.model_id})
            except Exception as exc:
                logger.exception("Failed to load local language model")
                self._model = None
                self._tokenizer = None
                raise ModelUnavailableError("The configured language model could not be loaded") from exc
