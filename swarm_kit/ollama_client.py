"""Minimal async streaming client for a local Ollama server.

No SDK, no API key, no cloud — this is the only thing standing between
this repo and a real local model. If Ollama isn't running, swarm.py
falls back to --demo (mock) mode automatically.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

DEFAULT_HOST = "http://localhost:11434"


class OllamaError(RuntimeError):
    pass


async def is_available(host: str = DEFAULT_HOST, timeout: float = 1.5) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{host}/api/tags")
            return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def stream_chat(
    model: str,
    messages: list[dict[str, str]],
    host: str = DEFAULT_HOST,
    timeout: float = 60.0,
    options: dict | None = None,
) -> AsyncIterator[str]:
    """Stream a chat completion from Ollama, yielding text chunks as they arrive."""
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", f"{host}/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise OllamaError(
                        f"Ollama returned {resp.status_code} for model '{model}': "
                        f"{body[:200]!r}. Did you `ollama pull {model}`?"
                    )
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Could not reach Ollama at {host}. Is it running? (`ollama serve`)"
        ) from e


async def chat_once(
    model: str,
    messages: list[dict[str, str]],
    host: str = DEFAULT_HOST,
    timeout: float = 20.0,
) -> str:
    """Non-streaming convenience call for short metadata asks (e.g. mood)."""
    payload = {"model": model, "messages": messages, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{host}/api/chat", json=payload)
            if r.status_code != 200:
                raise OllamaError(f"Ollama returned {r.status_code}: {r.text[:200]!r}")
            data = r.json()
            return data.get("message", {}).get("content", "")
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Could not reach Ollama at {host}. Is it running? (`ollama serve`)"
        ) from e
