#!/usr/bin/env python3
"""SLM Swarm Kit — watch tiny local models argue with each other.

Usage:
    python swarm.py --demo                       # zero setup, canned responses
    python swarm.py --demo --scenario pizza-debate
    python swarm.py                               # live, uses your local Ollama models
    python swarm.py --scenario moon-base-debate
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from swarm_kit.config import ROOT, Scenario, list_scenarios, load_personas, load_scenario
from swarm_kit.ollama_client import is_available
from swarm_kit.ui import SwarmApp


def pick_scenario_interactively() -> Path:
    scenarios = list_scenarios()
    print("\nAvailable scenarios:\n")
    for i, path in enumerate(scenarios):
        print(f"  [{i}] {path.stem}")
    choice = input("\nPick one (number): ").strip()
    try:
        return scenarios[int(choice)]
    except (ValueError, IndexError):
        print("Invalid choice.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch tiny local models argue.")
    parser.add_argument("--scenario", help="Scenario name (file stem under scenarios/)")
    parser.add_argument(
        "--topic",
        help='Your own debate topic, e.g. --topic "tabs vs spaces" '
        "(argued by the default Optimist vs Skeptic; requires a running Ollama)",
    )
    parser.add_argument(
        "--demo", action="store_true", help="Run with zero setup — no Ollama required"
    )
    args = parser.parse_args()

    if args.topic and args.scenario:
        print("Use either --topic or --scenario, not both.")
        sys.exit(1)

    if args.topic:
        if args.demo:
            print("--topic needs live models (there's no script for a custom topic).")
            print("Drop --demo, make sure Ollama is running, and try again.")
            sys.exit(1)
        if not asyncio.run(is_available()):
            print("\n--topic needs a running Ollama server, and none was found at")
            print("http://localhost:11434. Start it with `ollama serve`, pull the")
            print("default models (see personas/debate_default.yaml), and re-run.")
            print("Or try the scripted demo instead:  python swarm.py --demo\n")
            sys.exit(1)
        scenario = Scenario(
            name="custom-topic",
            mode="debate",
            topic=args.topic,
            participants=["optimist", "skeptic"],
            rounds=4,
            persona_file="debate_default.yaml",
        )
        personas = load_personas(ROOT / "personas" / scenario.persona_file)
        SwarmApp(scenario, personas, use_mock=False).run()
        return

    if args.scenario:
        scenario_path = ROOT / "scenarios" / f"{args.scenario}.yaml"
        if not scenario_path.exists():
            available = ", ".join(p.stem for p in list_scenarios())
            print(f"No such scenario: '{args.scenario}'. Available: {available}")
            sys.exit(1)
    else:
        scenario_path = pick_scenario_interactively()

    scenario = load_scenario(scenario_path)
    personas = load_personas(ROOT / "personas" / scenario.persona_file)

    use_mock = args.demo
    if not use_mock:
        if not asyncio.run(is_available()):
            print("\nNo local Ollama server found at http://localhost:11434.")
            print("Falling back to --demo mode (canned responses, no models needed).")
            print("To use real models: install Ollama, run `ollama serve`,")
            print(f"then `ollama pull <model>` for each model in personas/{scenario.persona_file},")
            print("and re-run without --demo.\n")
            use_mock = True

    app = SwarmApp(scenario, personas, use_mock)
    app.run()


if __name__ == "__main__":
    main()
