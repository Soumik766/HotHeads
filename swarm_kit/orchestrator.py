"""Round-robin debate loop.

Each persona sees the running transcript (as alternating user/assistant
turns from its own point of view) and responds in character, streamed
chunk by chunk so the UI can render it live. After each reply, the
persona is asked — separately, off to the side, not inline with the
visible dialogue — for a one-word read on its own mood, which the UI
shows as an emoji beside that turn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from . import mock, ollama_client
from .config import Persona, Scenario


@dataclass
class TurnEvent:
    persona_key: str
    round_idx: int
    kind: str  # "start" | "chunk" | "end"
    text: str = ""
    mood: str | None = None  # only set on "end" events


def _build_messages(
    persona: Persona, topic: str, transcript: list[tuple[str, str]]
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": persona.system_prompt}]
    messages.append(
        {
            "role": "user",
            "content": (
                f"The topic under debate is: {topic}\n"
                "Stay fully in character. Keep your reply to 2-3 sentences."
            ),
        }
    )
    for speaker, text in transcript:
        role = "assistant" if speaker == persona.name else "user"
        messages.append({"role": role, "content": f"{speaker}: {text}"})
    return messages


async def fetch_mood(persona: Persona, reply_text: str, host: str = ollama_client.DEFAULT_HOST) -> str:
    """Ask the persona, in one quick non-streamed call, how it's feeling.

    Kept as a separate call rather than an inline tag so the visible
    dialogue never has to be parsed/stripped of metadata — the reply
    stream stays exactly what the persona said, nothing more.
    """
    messages = [
        {"role": "system", "content": persona.system_prompt},
        {
            "role": "user",
            "content": (
                f'You just said: "{reply_text}"\n'
                "In exactly one lowercase word, name the emotion behind that. "
                "Respond with only the word."
            ),
        },
    ]
    try:
        text = await ollama_client.chat_once(persona.model, messages, host=host)
        word = text.strip().split()[0] if text.strip() else "neutral"
        return word.strip(".,!\"'").lower()
    except ollama_client.OllamaError:
        return "neutral"


async def run_debate(
    scenario: Scenario,
    personas: dict[str, Persona],
    use_mock: bool,
) -> AsyncIterator[TurnEvent]:
    transcript: list[tuple[str, str]] = []
    for round_idx in range(scenario.rounds):
        for key in scenario.participants:
            persona = personas[key]
            yield TurnEvent(key, round_idx, "start")
            full_text = ""
            mood = "neutral"
            if use_mock:
                line, mood = mock.get_turn(scenario.name, key, round_idx)
                async for chunk in mock.stream_line(line):
                    full_text += chunk
                    yield TurnEvent(key, round_idx, "chunk", chunk)
            else:
                try:
                    messages = _build_messages(persona, scenario.topic, transcript)
                    async for chunk in ollama_client.stream_chat(persona.model, messages):
                        full_text += chunk
                        yield TurnEvent(key, round_idx, "chunk", chunk)
                    mood = await fetch_mood(persona, full_text.strip())
                except ollama_client.OllamaError as e:
                    yield TurnEvent(key, round_idx, "chunk", f"\n[error: {e}]\n")
                    full_text = full_text or "(failed to respond)"
                    mood = "confused"
            transcript.append((persona.name, full_text.strip()))
            yield TurnEvent(key, round_idx, "end", full_text.strip(), mood=mood)
