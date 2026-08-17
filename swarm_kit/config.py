"""Load persona and scenario definitions from YAML files.

Personas and scenarios are pure data on purpose — no persona-specific
logic lives in code. Want a new character? Edit a YAML file. Want a new
debate? Edit a YAML file. That's the whole extension surface.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclasses.dataclass
class Persona:
    key: str
    name: str
    emoji: str
    color: str
    model: str
    system_prompt: str


@dataclasses.dataclass
class Scenario:
    name: str
    mode: str  # "debate" (pipeline mode is on the roadmap — see AGENTS.md)
    topic: str
    participants: list[str]
    rounds: int
    persona_file: str


def load_personas(path: str | Path) -> dict[str, Persona]:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    personas: dict[str, Persona] = {}
    for key, p in data["personas"].items():
        personas[key] = Persona(
            key=key,
            name=p["name"],
            emoji=p.get("emoji", "\U0001F916"),
            color=p.get("color", "white"),
            model=p.get("model", "qwen2.5:1.5b"),
            system_prompt=p["system_prompt"].strip(),
        )
    return personas


def load_scenario(path: str | Path) -> Scenario:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Scenario(
        name=data["name"],
        mode=data.get("mode", "debate"),
        topic=data["topic"],
        participants=list(data["participants"]),
        rounds=int(data.get("rounds", 4)),
        persona_file=data["persona_file"],
    )


def list_scenarios() -> list[Path]:
    return sorted((ROOT / "scenarios").glob("*.yaml"))
