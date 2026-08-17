"""Shared mood -> emoji mapping.

Every persona reports a one-word feeling after each turn — scripted in
mock.py for --demo, asked directly of the model in live mode (see
orchestrator.fetch_mood). This module just turns that word into
something you can read at a glance.
"""
from __future__ import annotations

MOOD_EMOJI: dict[str, str] = {
    "smug": "😏", "amused": "😄", "gracious": "🙂", "proud": "😌",
    "annoyed": "😠", "dismissive": "🙄", "reluctant": "😒", "frustrated": "😤",
    "delighted": "🤩", "unconvinced": "🤨", "gleeful": "😈", "bored": "😑",
    "alarmed": "😨", "curious": "🤔", "cold": "🥶", "warm": "🥰",
    "defiant": "🔥", "resigned": "😔", "irritated": "😤", "confident": "😎",
    "skeptical": "🤨", "excited": "🤩", "sarcastic": "😏", "triumphant": "🏆",
    "defeated": "😞", "neutral": "😐", "satisfied": "😊", "dreamy": "🌙",
    "hopeful": "🤞", "smirking": "😏", "confused": "😕", "angry": "😡",
    "calm": "😌", "impatient": "😑", "intrigued": "🧐", "unimpressed": "😒",
}
DEFAULT_EMOJI = "😐"


def emoji_for(mood: str | None) -> str:
    if not mood:
        return DEFAULT_EMOJI
    key = mood.strip().lower().strip(".!,\"'")
    return MOOD_EMOJI.get(key, DEFAULT_EMOJI)
