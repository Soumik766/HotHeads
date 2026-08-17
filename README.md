# 🔥 HotHeads

**Tiny local LLMs argue, discuss, and reach a verdict — live, in your browser.**

No API keys. No cloud. No cost. Pick a cast of characters (or write your
own), pit them against each other, and watch the fight unfold one bubble
at a time — mood-driven faces, a heat gauge, the works. Everything runs
on models you pull yourself via [Ollama](https://ollama.com).

```bash
git clone git@github.com:Soumik766/HotHeads.git
cd HotHeads
python start.py
```

One file, zero flags. `start.py` installs missing Python packages,
verifies Ollama is installed and running, downloads any missing models,
warms them up, and opens HotHeads in your browser. If anything's
missing it tells you exactly what and gives you a Retry button — it
never just hangs.

<!-- 🎬 Drop a recorded GIF here — this is the single highest-leverage
     thing you can add to this README. -->
<!-- ![demo](docs/demo.gif) -->

## Two modes

**🔥 Fight** — a formal debate with rounds, closing arguments, and a
heat gauge that climbs as tempers flare.

**💬 Discuss** — a casual group chat. Ask it anything ("GOD vs me — who
wins?") and watch the cast text like real people: one-liners, `*sips
tea*` action beats, the occasional emoji, direct call-outs ("do you
agree, Mila?"), and a final verdict once they've actually talked it out.
Replies land at human speed — sometimes instant, sometimes they leave
you on read for a few seconds.

## Build your own cast

Click **🎭 Personas** (bottom-left) to:
- Edit any built-in persona's prompt — turn the Skeptic into a
  conspiracy theorist, the Optimist into a cult leader, whatever you want.
- **Add a persona** from scratch: name, emoji, personality prompt, and
  any model Ollama supports. Pick an installed model and it's ready
  instantly; pick one you don't have and HotHeads downloads it for you,
  with live progress, right from the picker.
- Mix and match any 2+ personas per fight — hothead, monk, brat,
  whatever cast you want in the ring.

Every persona keeps its prompt, stays in character, and gets a random
human name each fight so it feels like people talking, not model
checkpoints.

## What's actually happening

```
webui/server.py     aiohttp app: pre-flight checks, persona/model management,
                     runs the debate loop, streams turns over SSE
webui/index.html     the whole UI — mood faces, pacing, heat gauge, personas modal
swarm_kit/            the reusable core: config, Ollama client, orchestrator
personas/*.yaml       built-in character definitions (extendable from the UI)
```

Each persona is a genuinely separate model call — they see the running
transcript and respond in character, which is why the fight has real
back-and-forth logic instead of parallel monologues. After every reply
there's a quick separate call asking the persona to name its mood in
one word, which drives both the emoji face and the heat gauge.

## Also included: a terminal mode

The original terminal experience still works if you'd rather watch it
in a TUI than a browser:

```bash
pip install -r requirements.txt
python swarm.py --demo                    # zero setup, scripted responses
python swarm.py --scenario pizza-debate   # live, needs Ollama + pulled models
python swarm.py --topic "tabs vs spaces"  # your own topic, Optimist vs Skeptic
```

See `AGENTS.md` for the full architecture write-up if you're extending
this with an AI coding assistant.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) — `start.py` will tell you if it's missing

## License

MIT — see [LICENSE](LICENSE).
