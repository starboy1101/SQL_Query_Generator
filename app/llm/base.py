from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GenerationInput:
    prompt: str
    question: str
    dialect: str
    max_rows: int


class LLMBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    def generate(self, generation_input: GenerationInput) -> str: ...

    def warmup(self) -> None: ...
