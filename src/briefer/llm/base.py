"""The single LLM interface (§4.4). Adapters implement `complete`; nothing else in the
pipeline knows which provider is in use."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypedDict


class Message(TypedDict):
    role: str      # system | user | assistant
    content: str


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResult:
    text: str
    usage: Usage = field(default_factory=Usage)
    cached: bool = False


class LLMError(RuntimeError):
    pass


class Adapter(Protocol):
    def complete(self, messages: list[Message], json_schema: dict | None, max_tokens: int,
                 *, model: str, temperature: float, seed: int | None) -> LLMResult: ...
