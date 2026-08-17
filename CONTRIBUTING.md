# Contributing to HotHeads

Thanks for wanting to throw another persona into the ring. This repo is
meant to be forked and messed with — here's how to send changes back.

## Setup

```bash
git clone https://github.com/<your-fork>/HotHeads.git
cd HotHeads
python start.py          # web UI, needs Ollama
# or, for the terminal mode / running tests:
pip install -r requirements.txt -r requirements-dev.txt
```

You don't need Ollama installed to work on most of the codebase — the
test suite and `--demo` mode are fully offline. You only need Ollama
running if you're testing a live Fight or Discuss session end to end.

## Workflow

1. Fork the repo and create a branch off `main`:
   `git checkout -b your-change-name`
2. Make your change.
3. Run the tests: `pytest tests/ -v` — all green before you open a PR.
4. Commit with a message that says *why*, not just *what*.
5. Push to your fork and open a pull request against `main`.

Keep PRs focused — one feature or fix per PR is much easier to review
than a bundle of unrelated changes.

## Easy ways to contribute

You don't need to touch Python for most of these:

- **New personas** — add one to `personas/debate_default.yaml` (name,
  emoji, color, model, system_prompt) or build one live in the app via
  **🎭 Personas → Add persona**, then export its prompt back into the
  YAML file in a PR.
- **New scenarios** — add a YAML file under `scenarios/`, and a
  matching mock script in `swarm_kit/mock.py` so `--demo` still works
  for it. `test_config.py` will fail loudly if you miss a persona
  reference.
- **Bug reports** — open an issue with what you ran, what you expected,
  and what happened instead. Include your OS and whether you were using
  the web UI or terminal mode.
- **Bigger features** — open an issue to discuss the approach first,
  especially anything touching `webui/server.py` or the orchestrator;
  saves everyone a rewritten PR later.

## Code style

- Type hints on all function signatures.
- Dataclasses for structured data (see `swarm_kit/config.py`).
- Async generators for anything that streams — don't buffer a full
  reply before yielding it. The live, chunk-by-chunk reveal is the
  actual product.
- Keep dependencies light. Current deps (`textual`, `rich`, `httpx`,
  `pyyaml`, `aiohttp`) are deliberate — if your change needs a new one,
  say why in the PR description.

See [AGENTS.md](AGENTS.md) for the full architecture write-up,
including the hard constraints (`--demo` must always work with zero
external dependencies is the big one) and file-by-file data flow.

## Testing

```bash
pytest tests/ -v
```

All tests are offline by design. If your change talks to Ollama, mock
the HTTP layer rather than requiring a live server for tests to pass —
see the existing tests for the pattern.

## Reporting security issues

If you find something that could leak local data or execute untrusted
input, please open an issue describing the problem — this is a hobby
project with no formal security process, but real reports are taken
seriously and fixed promptly.

## Code of conduct

Be decent. Disagree about code, not about people. Everything else
follows from that.
