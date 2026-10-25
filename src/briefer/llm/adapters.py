"""Provider adapters: ollama (local), openai_compatible (vLLM, EU endpoints) and anthropic."""

from __future__ import annotations

import json
import os

import httpx

from .base import LLMError, LLMResult, Message, Usage


class OllamaAdapter:
    def __init__(self, base_url: str, num_ctx: int = 8192, **_: object) -> None:
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx

    def complete(self, messages: list[Message], json_schema: dict | None, max_tokens: int,
                 *, model: str, temperature: float, seed: int | None) -> LLMResult:
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens,
                        "num_ctx": self.num_ctx, **({"seed": seed} if seed is not None else {})},
        }
        if json_schema:
            body["format"] = json_schema
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=600)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"ollama: {e}") from e
        data = r.json()
        return LLMResult(
            text=data["message"]["content"],
            usage=Usage(data.get("prompt_eval_count", 0), data.get("eval_count", 0)),
        )


def _api_key(env: str | None) -> str:
    key = os.environ.get(env or "", "")
    if not key:
        raise LLMError(f"missing API key: set {env} in the environment or .env")
    return key


class OpenAICompatibleAdapter:
    def __init__(self, base_url: str, api_key_env: str | None = None, **_: object) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env

    def complete(self, messages: list[Message], json_schema: dict | None, max_tokens: int,
                 *, model: str, temperature: float, seed: int | None) -> LLMResult:
        body: dict = {"model": model, "messages": messages, "max_tokens": max_tokens,
                      "temperature": temperature}
        if seed is not None:
            body["seed"] = seed
        if json_schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "output", "schema": json_schema, "strict": False}}
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body, timeout=300,
                           headers={"Authorization": f"Bearer {_api_key(self.api_key_env)}"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"openai_compatible: {type(e).__name__}") from e
        data = r.json()
        u = data.get("usage", {})
        return LLMResult(text=data["choices"][0]["message"]["content"],
                         usage=Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0)))


class AnthropicAdapter:
    def __init__(self, base_url: str, api_key_env: str | None = None, **_: object) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env

    def complete(self, messages: list[Message], json_schema: dict | None, max_tokens: int,
                 *, model: str, temperature: float, seed: int | None) -> LLMResult:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        if json_schema:
            system += ("\n\nRespond with a single JSON object only, matching this JSON schema:\n"
                       + json.dumps(json_schema))
        body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
                "system": system,
                "messages": [m for m in messages if m["role"] != "system"]}
        try:
            r = httpx.post(f"{self.base_url}/v1/messages", json=body, timeout=300, headers={
                "x-api-key": _api_key(self.api_key_env), "anthropic-version": "2023-06-01"})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"anthropic: {type(e).__name__}") from e
        data = r.json()
        text = "".join(b.get("text", "") for b in data["content"] if b["type"] == "text")
        u = data.get("usage", {})
        return LLMResult(text=text, usage=Usage(u.get("input_tokens", 0),
                                                u.get("output_tokens", 0)))


ADAPTERS = {
    "ollama": OllamaAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
}
