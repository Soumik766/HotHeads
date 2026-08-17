# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

HotHeads: a web UI (and terminal fallback) for watching small local
language models (SLMs) argue, discuss, and reach a verdict — streamed
live, one bubble per model. The whole point is that it's watchable:
`python swarm.py --demo` should run in under 10 seconds with zero setup
and look alive; `python start.py` is the one-file entry point for the
full web experience.

Two audiences use this repo differently:
1. People who clone it to *watch* the demo. Never break `--demo` mode.
2. People who fork it to build their own cast. Keep the extension
   surface (YAML files, the Personas UI) simple enough that they don't
   need to touch Python at all for the common case.

## Architecture

```
start.py                  One-file entry point — deps, Ollama setup, launches webui/server.py
webui/
  server.py                aiohttp app: pre-flight checks, persona/model management,
                            SSE debate stream (Fight + Discuss modes)
  index.html                the whole UI — mood faces, pacing, heat gauge, personas modal
  personas.json              user-created personas + prompt overrides (gitignored-ish, lives locally)
swarm.py                  Terminal CLI entrypoint — parses args, loads config, launches the TUI
swarm_kit/
  config.py                Loads personas/*.yaml and scenarios/*.yaml into dataclasses
  ollama_client.py          Thin async streaming wrapper around the Ollama REST API
  mock.py                   Canned, scripted responses — powers --demo, needs no models
  orchestrator.py           The terminal debate loop (async generator of TurnEvents)
  ui.py                     Textual app: one PersonaPane per participant, live-updating
personas/*.yaml            Built-in character definitions: name, emoji, color, model, system_prompt
scenarios/*.yaml           A topic + which personas argue about it + how many rounds
tests/                     pytest, all offline — no Ollama, no network, no GPU required
```

Data flow (terminal mode): `swarm.py` loads a `Scenario` and its
`Persona`s from YAML → `orchestrator.run_debate()` yields `TurnEvent`s
(start/chunk/end) as an async generator, sourcing text from either
`mock.py` (--demo) or `ollama_client.py` (live) → `ui.py`'s `SwarmApp`
consumes those events and paints them into per-persona panes in real
time.

Data flow (web mode): `webui/server.py` builds `Persona`s from
`personas/*.yaml` plus any overrides/customs in `webui/personas.json`,
hands out random display names per fight, runs its own
`run_web_debate()` loop (Fight or Discuss mode, with a closing round),
and streams events over Server-Sent Events to `webui/index.html`, which
paces the reveal (typing indicator → message → reading pause) instead
of raw streaming.

Each `TurnEvent`/end-event carries a `mood: str` — a one-word feeling,
scripted per-line in `mock.py` for demo mode, or fetched via a separate
non-streamed `ollama_client.chat_once()` call in live mode
(`orchestrator.fetch_mood()`). `swarm_kit/moods.py` maps that word to
an emoji; `webui/server.py` additionally normalizes noun-form moods
("excitement" → "excited") since small models are inconsistent about
this. The mood call is deliberately kept **out of band** from the main
streamed reply — the visible dialogue is never parsed for embedded
tags, so what streams into the UI is exactly what the persona said,
nothing appended or stripped.

**UI internals worth knowing before you touch `swarm_kit/ui.py`:**
Textual's `RichLog.write()` creates a new entry per call, not an
in-place append. Streaming word-by-word chunks directly into a
`RichLog` renders as one word per line, not flowing text. `PersonaPane`
works around this with two widgets: a `Static` (`#live-{key}`) that
holds the in-progress turn and gets its `.update()` called on every
chunk (this is what gives the live-typing effect, updating in place),
and a `RichLog` (`#history-{key}`) that only receives a `write()` once
per *finished* turn — the full line plus its mood emoji, committed as a
single scrollback entry. If you're adding a feature that touches
per-chunk rendering, keep using the `Static` for anything that updates
mid-turn; only write finished lines to the `RichLog`.

## Hard constraints — do not break these

- **`--demo` must always work with zero external dependencies.** No
  network calls, no Ollama, no downloaded models. This is the whole
  reason people give the repo a chance. If you add a scenario, add a
  matching mock script (line **and** mood) in `mock.py` in the same PR
  — `tests/test_moods.py` will fail if a scripted mood has no emoji
  mapping in `moods.py`.
- **Personas and scenarios are pure data.** Don't hardcode persona-name
  checks or scenario-name checks anywhere except `mock.py` (which by
  necessity keys scripted lines by scenario/persona name). The
  orchestrator and UI must work for *any* YAML-defined persona/scenario
  without code changes.
- **Streaming stays streaming.** Don't collapse `stream_chat` /
  `stream_line` into a single blocking call that returns full text —
  the live, word-by-word reveal is the actual product. If you touch
  `orchestrator.py`, keep `TurnEvent` chunks small.
- **The UI must degrade gracefully without Ollama.** `swarm.py` checks
  `is_available()` and falls back to `--demo` automatically with a
  clear message — don't replace that with a hard crash. The web UI's
  pre-flight checks in `webui/server.py`'s `SetupManager` serve the
  same purpose for `start.py`.

## Adding a new scenario (terminal mode, no Python required)

1. Add a script to `personas/*.yaml` if you need a persona that doesn't
   exist yet (name, emoji, color, model, system_prompt).
2. Add a new file to `scenarios/`, e.g. `scenarios/my_debate.yaml`:
   ```yaml
   name: my-debate
   mode: debate
   topic: "Your topic here"
   persona_file: debate_default.yaml
   participants: [persona_key_a, persona_key_b]
   rounds: 4
   ```
3. Add a matching mock script to `mock.py`'s `SCRIPTS` dict, keyed by
   `name` and each participant's key, so `--demo` works for it too.
4. Run `pytest tests/` — `test_config.py` will fail loudly if a
   scenario references a persona key that doesn't exist.

(In the web UI, personas and fights are managed live through the
Personas modal and the topic box — no YAML editing required.)

## Roadmap (do not build unless asked)

The original design also included a **pipeline mode** — Planner →
Critic → Executor → Judge, an "organ system" for actually solving
tasks rather than debating them, as opposed to the current round-robin
`debate` mode. `Scenario.mode` already has a `mode` field reserved for
this (`"debate"` today). If asked to build it: add `run_pipeline()` to
`orchestrator.py` alongside `run_debate()`, dispatch on `scenario.mode`
in `swarm.py`, and keep the same `TurnEvent` protocol so `ui.py` needs
minimal changes. Don't build this speculatively — it's a deliberate
scope cut.

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All tests are offline by design (`test_mock.py`, `test_config.py`).
If you add a feature that talks to Ollama, mock the HTTP layer rather
than requiring a live server for tests to pass.

## Style

- Type hints on all function signatures.
- Dataclasses for structured data (see `config.py`, `orchestrator.py`).
- Async generators for anything that streams (`mock.py`,
  `ollama_client.py`, `orchestrator.py`) — don't buffer full responses
  before yielding.
- Keep `swarm_kit/` dependency-light. Current deps (`textual`, `rich`,
  `httpx`, `pyyaml`, `aiohttp`) are deliberate; think twice before
  adding more.
