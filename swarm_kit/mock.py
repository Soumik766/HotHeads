"""Canned, deterministic responses so the demo runs with zero setup —
no Ollama, no downloaded models, no GPU, no wait. Just:

    python swarm.py --demo

This exists so a stranger can clone the repo and see the whole idea
work in under 10 seconds, before they've committed to installing
anything. Real scenarios still need real models — see ollama_client.py.

Each scripted line carries its own mood tag so --demo exercises the
same "beside each response, how do they feel" feature that live mode
gets from actually asking the model.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

# scenario_name -> persona_key -> list of (line, mood), one per round (cycles)
SCRIPTS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "pizza-debate": {
        "optimist": [
            ("Pineapple on pizza is a triumph of sweet-savory balance. Fight me.", "smug"),
            ("You're not against pineapple, you're against joy. There's a difference.", "amused"),
            ("Fine — compromise: pineapple on HALF the pizza. Democracy in action.", "gracious"),
            ("I'll accept 'situational' as a partial victory and retreat with honor.", "proud"),
        ],
        "skeptic": [
            ("Pineapple is a fruit. Fruit does not belong near molten cheese.", "annoyed"),
            ("That is not an argument, that is a vibe. I require evidence.", "dismissive"),
            ("...half the pizza is acceptable. This is the only concession I will make today.", "reluctant"),
            ("Noted for the record: I did not lose, I compromised. There's a difference.", "smug"),
        ],
    },
    "moon-base-debate": {
        "engineer": [
            ("Lava tubes. Free radiation shielding, stable temperature, done. Next question.", "confident"),
            ("Surface habitats need meters of regolith shielding just to survive one solar flare.", "irritated"),
            ("Fine — hybrid: surface for solar collection, lava tubes for actually living.", "resigned"),
            ("That's a base I'd sign off on. Ship it.", "satisfied"),
        ],
        "romantic": [
            ("But imagine the view — Earth rising over a crater rim every dawn.", "dreamy"),
            ("A view no one survives to enjoy isn't a view, it's a eulogy.", "defiant"),
            ("A skylight, then. One window down into the tube. Meet me halfway.", "hopeful"),
            ("One glass dome, one sunrise. I can work with that.", "satisfied"),
        ],
    },
}


async def stream_line(text: str, delay: float = 0.02) -> AsyncIterator[str]:
    """Yield a canned line word by word to simulate token-by-token streaming."""
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        if delay:
            await asyncio.sleep(delay)


def get_turn(scenario: str, persona_key: str, round_idx: int) -> tuple[str, str]:
    """Returns (line, mood) for this persona's turn in this round."""
    script = SCRIPTS.get(scenario, {})
    lines = script.get(persona_key)
    if not lines:
        return (
            f"[[no mock script for persona '{persona_key}' in scenario '{scenario}']]",
            "confused",
        )
    return lines[round_idx % len(lines)]
