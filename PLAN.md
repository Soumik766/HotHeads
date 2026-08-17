# 🐝 SLM Swarm Kit — The Plan

> **One sentence:** give the swarm a topic, and several tiny local
> models — each a distinct character — argue about it live in your
> terminal, with a mood reaction beside every line.

---

## The idea, in plain words

1. **You give an input** — a topic, a question, anything debatable.
2. **Agents come from Ollama** — each participant is a real, separate
   small model (1B–3B class) running locally on your machine, wearing
   a persona defined in plain YAML: a name, an emoji, a colour, a model
   checkpoint, and a system prompt that gives it an attitude.
3. **They argue** — round-robin. Each agent sees the running transcript
   and answers *the other agent*, in character. The disagreement is
   real model behaviour, not a script.
4. **You watch** — a terminal UI shows one colour-coded pane per agent,
   text streaming in word by word like live typing, and after every
   finished line the agent reports its own feeling, shown as an emoji
   reaction (`😏 smug`, `😤 irritated`, `🌙 dreamy`).

No API keys. No cloud. No cost. And a `--demo` mode with scripted
dialogue so the whole thing runs in ten seconds with nothing installed
but Python.

---

## How a single turn flows

```
                     you
                      │  topic ("Does pineapple belong on pizza?")
                      ▼
              ┌───────────────┐
              │  orchestrator │  round-robin: whose turn is it?
              └───────┬───────┘
                      │  transcript so far + persona system prompt
                      ▼
              ┌───────────────┐
              │ Ollama model  │  e.g. qwen2.5:1.5b as "Optimist 🌞"
              └───────┬───────┘
                      │  streamed reply, chunk by chunk
                      ▼
              ┌───────────────┐
              │  terminal UI  │  live-typing line in Optimist's pane
              └───────┬───────┘
                      │  when the line finishes…
                      ▼
              ┌───────────────┐
              │  mood call    │  "in one word, how do you feel?"
              └───────┬───────┘
                      │  "smug"
                      ▼
                 😏 smug  ← reaction committed beside the line
```

Then the next agent takes its turn, seeing everything said so far —
which is why the argument has actual back-and-forth logic instead of
being two monologues.

## What the screen looks like

```
┌─ 🌞 Optimist ✓ ─────────────────┐  ┌─ 🧊 Skeptic ✻ ──────────────────┐
│ ── round 1 ──                    │  │ ── round 1 ──                    │
│ Pineapple on pizza is a triumph  │  │ Pineapple is a fruit. Fruit does │
│ of sweet-savory balance. Fight   │  │ not belong near molten cheese.   │
│ me.  😏 smug                     │  │ 😠 annoyed                       │
│                                  │  │                                  │
│ ── round 2 ──                    │  │ ── round 2 ──                    │
│ You're not against pineapple,    │  │ That is not an argument, that    │
│ you're against joy.  😄 amused   │  │ is a vibe. I require evi▌        │
└──────────────────────────────────┘  └──────────────────────────────────┘
```

The `✻` in the border means that agent is thinking; the half-typed
line is streaming in live. `q` quits, `r` restarts.

---

## The three ways to start an argument

| Command | What happens | Needs Ollama? |
|---|---|---|
| `python swarm.py --demo` | Scripted debate, canned moods — the 10-second first impression | No |
| `python swarm.py --scenario pizza-debate` | A YAML-defined matchup with real models | Yes |
| `python swarm.py --topic "tabs vs spaces"` | **Your** input, argued by the default duo (Optimist vs Skeptic) | Yes |

`--topic` is the "give it an input" path: no YAML editing, just type
the fight you want to see. Custom topics need live models — there's no
script for a topic nobody predicted — so if Ollama isn't running,
`swarm.py` says so plainly instead of showing placeholder junk.

---

## The pieces

| File | Job |
|---|---|
| `swarm.py` | CLI: pick a scenario / topic / demo mode, launch the UI |
| `personas/*.yaml` | Who the agents *are* — name, emoji, colour, model, attitude |
| `scenarios/*.yaml` | Who fights whom, about what, for how many rounds |
| `swarm_kit/orchestrator.py` | The debate loop; yields start/chunk/end events |
| `swarm_kit/ollama_client.py` | Streaming chat + one-shot calls to local Ollama |
| `swarm_kit/mock.py` | Scripted lines + moods that power `--demo` |
| `swarm_kit/moods.py` | mood word → emoji |
| `swarm_kit/ui.py` | The watchable part: panes, live typing, reactions |

Personas and scenarios are **pure data** — creating a new agent or a
new fight never requires touching Python.

---

## Design bets (and why)

- **Small models on purpose.** At 1B–3B scale, models are opinionated
  and inconsistent — which is exactly what makes a debate fun to watch.
  This repo treats small-model jank as the product, not the flaw.
- **Local-only.** Zero API cost means zero hesitation to run it, fork
  it, and leave it running. Whatever the models will or won't say is a
  property of the checkpoints you pull, not a layer we add.
- **Demo mode is sacred.** Most people decide in ten seconds. `--demo`
  must always work with nothing but `pip install -r requirements.txt`.
- **Moods are out-of-band.** The feeling is fetched in a separate tiny
  call *after* the reply, never embedded as tags inside the dialogue —
  so what streams on screen is exactly what the agent said.

---

## Roadmap

- [x] v0.1 — debate loop, two scenarios, demo mode, terminal UI
- [x] v0.2 — mood reactions beside every line; `--topic` for direct user input
- [ ] v0.3 — **pipeline mode**: Planner → Critic → Executor → Judge, a
      swarm that *solves* a task instead of debating it (`Scenario.mode`
      already reserves the slot)
- [ ] More personas + a scenario gallery from contributors
- [ ] Judge agent that declares a winner at the end of a debate
- [ ] Optional transcript export (`--save argument.md`)

---

*See `README.md` for setup, `AGENTS.md` for contributor/agent rules.*
