"""Textual UI: one live-updating, colour-coded pane per persona.

This is the whole point of the repo — you don't read a transcript,
you *watch* the argument happen in real time, one pane per model, with
a mood emoji beside each finished line.

Each pane has two parts:
  - a RichLog holding finished turns (scrollable history)
  - a single live Static line showing the *current* turn typing out

RichLog.write() creates a new entry per call, so streaming chunks
straight into it would render one word per line. Instead we buffer the
in-progress turn in the Static widget (which updates in place) and only
commit the finished, whole line to the RichLog once the turn ends.
"""
from __future__ import annotations

import asyncio
import math

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, RichLog, Static

from .config import Persona, Scenario
from .moods import emoji_for
from .orchestrator import run_debate

STATUS_ICON = {"waiting": "\u2026", "thinking": "\u2727", "done": "\u2713"}


class PersonaPane(Static):
    """A bordered pane: scrolling history + one live-typing line."""

    status: reactive[str] = reactive("waiting")

    def __init__(self, persona: Persona, **kwargs):
        super().__init__(**kwargs)
        self.persona = persona
        self._live_buffer = ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield RichLog(wrap=True, markup=False, id=f"history-{self.persona.key}")
            yield Static("", id=f"live-{self.persona.key}", classes="live-line")

    def on_mount(self) -> None:
        self.styles.border = ("round", self.persona.color)
        self._refresh_title()

    def _refresh_title(self) -> None:
        icon = STATUS_ICON.get(self.status, "")
        self.border_title = f"{self.persona.emoji} {self.persona.name}  {icon}"

    def set_status(self, status: str) -> None:
        self.status = status
        self._refresh_title()

    def new_turn(self, round_idx: int) -> None:
        self.query_one(RichLog).write(
            Text(f"\n\u2500\u2500 round {round_idx + 1} \u2500\u2500", style=f"bold {self.persona.color}")
        )
        self._live_buffer = ""
        self.query_one(f"#live-{self.persona.key}", Static).update("")

    def append_chunk(self, chunk: str) -> None:
        self._live_buffer += chunk
        self.query_one(f"#live-{self.persona.key}", Static).update(self._live_buffer)

    def finish_turn(self, mood: str | None) -> None:
        """Commit the completed line to history, tagged with a mood emoji."""
        emoji = emoji_for(mood)
        label = (mood or "neutral").strip()
        self.query_one(RichLog).write(Text(f"{self._live_buffer}  {emoji} {label}"))
        self._live_buffer = ""
        self.query_one(f"#live-{self.persona.key}", Static).update("")


class SwarmApp(App):
    """The whole demo: N personas, one grid, one live argument."""

    CSS = """
    Screen {
        background: $surface;
    }
    Grid {
        grid-gutter: 1 2;
        padding: 1 2;
    }
    PersonaPane {
        border: round white;
        padding: 0 1;
        height: 100%;
    }
    PersonaPane > Vertical {
        height: 100%;
    }
    RichLog {
        background: transparent;
        height: 1fr;
    }
    .live-line {
        background: transparent;
        color: $text-muted;
        text-style: italic;
        height: auto;
        min-height: 1;
    }
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "restart", "Restart")]

    def __init__(self, scenario: Scenario, personas: dict[str, Persona], use_mock: bool):
        super().__init__()
        self.scenario = scenario
        self.personas = personas
        self.use_mock = use_mock
        self.panes: dict[str, PersonaPane] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        n = len(self.scenario.participants)
        cols = 2 if n > 1 else 1
        rows = math.ceil(n / cols)
        with Grid() as grid:
            grid.styles.grid_size_columns = cols
            grid.styles.grid_size_rows = rows
            for key in self.scenario.participants:
                pane = PersonaPane(self.personas[key], id=f"pane-{key}")
                self.panes[key] = pane
                yield pane
        yield Footer()

    def on_mount(self) -> None:
        mode_label = "DEMO (mock)" if self.use_mock else "LIVE (Ollama)"
        self.title = f"SLM Swarm \u2014 {self.scenario.name} [{mode_label}]"
        self.sub_title = self.scenario.topic
        self.run_worker(self.run_scenario(), exclusive=True)

    async def run_scenario(self) -> None:
        current_round = -1
        async for event in run_debate(self.scenario, self.personas, self.use_mock):
            pane = self.panes[event.persona_key]
            if event.kind == "start":
                if event.round_idx != current_round:
                    current_round = event.round_idx
                    for p in self.panes.values():
                        p.new_turn(current_round)
                pane.set_status("thinking")
            elif event.kind == "chunk":
                pane.append_chunk(event.text)
            elif event.kind == "end":
                pane.finish_turn(event.mood)
                pane.set_status("done")
            await asyncio.sleep(0)  # yield control so the UI can repaint

    def action_restart(self) -> None:
        current_round = -1
        for pane in self.panes.values():
            pane.query_one(RichLog).clear()
            pane.set_status("waiting")
        self.run_worker(self.run_scenario(), exclusive=True)
