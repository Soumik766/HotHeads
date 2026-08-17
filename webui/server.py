"""HotHeads — local web UI server.

One aiohttp app that serves:
  - the single-page UI (webui/index.html)
  - setup verification + auto-fix (start Ollama, pull missing models, warm them)
  - persona management (edit prompts, add personas backed by any Ollama model)
  - model catalog + on-demand downloads with progress
  - past chats (JSON files under chats/)
  - a live debate/discussion as Server-Sent Events (random display names, closing round)
  - a solo 1:1 chat where a single persona always argues the other side

Launched by start.py — not meant to be run directly by end users.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import random
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from aiohttp import web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from swarm_kit import ollama_client  # noqa: E402
from swarm_kit.config import Persona, load_personas  # noqa: E402
from swarm_kit.moods import emoji_for  # noqa: E402
from swarm_kit.orchestrator import _build_messages, fetch_mood  # noqa: E402

CHATS_DIR = ROOT / "chats"
CHATS_DIR.mkdir(exist_ok=True)
PERSONA_FILE = ROOT / "personas" / "debate_default.yaml"
CUSTOM_FILE = Path(__file__).parent / "personas.json"
OLLAMA_HOST = ollama_client.DEFAULT_HOST

# Random display names handed out per fight — deliberately silly instead of
# normal human names, so the cast always feels a little unhinged before
# anyone's even said anything.
NAMES = [
    "Dried Milk", "Expired Milk", "Frozen Tea", "Stale Bread", "Burnt Toast",
    "Flat Soda", "Soggy Cereal", "Moldy Cheese", "Lukewarm Coffee",
    "Wilted Lettuce", "Cracked Egg", "Melted Ice Cream", "Squished Banana",
    "Overcooked Rice", "Spoiled Yogurt", "Rotten Tomato", "Crushed Chips",
    "Deflated Balloon", "Broken Umbrella", "Left Sock", "Tangled Charger",
    "Empty Wallet", "Rusty Spoon", "Chipped Mug", "Sticky Remote",
    "Cold Pizza", "Warm Beer", "Flat Tire", "Dead Battery", "Faded Jeans",
    "Lost Receipt", "Crumpled Napkin", "Squeaky Chair", "Leaky Pen",
    "Foggy Mirror", "Burnt Popcorn", "Melted Crayon", "Wobbly Table",
    "Static Sock", "Damp Firewood",
]

PALETTE = ["yellow", "cyan", "green", "magenta", "red", "blue"]

# Small-model catalog for "Add persona" (approx download sizes).
MODEL_CATALOG = [
    {"name": "qwen2.5:0.5b", "size": "398 MB"},
    {"name": "tinyllama:1.1b", "size": "638 MB"},
    {"name": "qwen2.5:1.5b", "size": "986 MB"},
    {"name": "deepseek-r1:1.5b", "size": "1.1 GB"},
    {"name": "llama3.2:1b", "size": "1.3 GB"},
    {"name": "gemma2:2b", "size": "1.6 GB"},
    {"name": "smollm2:1.7b", "size": "1.8 GB"},
    {"name": "qwen2.5:3b", "size": "1.9 GB"},
    {"name": "llama3.2:3b", "size": "2.0 GB"},
    {"name": "phi3:mini", "size": "2.2 GB"},
]

STAY_IN_CHARACTER = (
    " Keep every reply to 2-3 sentences. Say what you actually think, plainly,"
    " without hedging or disclaimers. Never break character, never mention"
    " that you are an AI or a language model."
)

# How hot each mood runs, 0 (ice) to 3 (open flame). Feeds the heat gauge.
MOOD_HEAT: dict[str, int] = {
    "angry": 3, "frustrated": 3, "defiant": 3, "irritated": 3, "furious": 3,
    "annoyed": 2, "smug": 2, "sarcastic": 2, "dismissive": 2, "impatient": 2,
    "unconvinced": 2, "skeptical": 2, "unimpressed": 2, "gleeful": 2,
    "triumphant": 2, "alarmed": 2,
    "amused": 1, "confident": 1, "excited": 1, "curious": 1, "delighted": 1,
    "intrigued": 1, "hopeful": 1, "proud": 1, "smirking": 1, "reluctant": 1,
    "bored": 1, "resigned": 1, "defeated": 1, "confused": 1,
}

# Small models often answer with the noun form ("excitement") instead of the
# adjective the emoji/heat tables use — normalize before lookup.
MOOD_ALIASES: dict[str, str] = {
    "excitement": "excited", "confusion": "confused", "anger": "angry",
    "amusement": "amused", "frustration": "frustrated", "annoyance": "annoyed",
    "skepticism": "skeptical", "curiosity": "curious", "boredom": "bored",
    "delight": "delighted", "pride": "proud", "calmness": "calm",
    "confidence": "confident", "defiance": "defiant", "sarcasm": "sarcastic",
    "smugness": "smug", "triumph": "triumphant", "impatience": "impatient",
    "irritation": "irritated", "wistfulness": "dreamy", "hope": "hopeful",
    "hopefulness": "hopeful", "respect": "gracious", "respectful": "gracious",
    "passionate": "defiant", "determined": "confident", "playful": "amused",
    "enthusiasm": "excited", "enthusiastic": "excited", "disbelief": "unconvinced",
    "doubt": "skeptical", "doubtful": "skeptical", "dismay": "alarmed",
    "optimism": "hopeful", "optimistic": "hopeful", "disdain": "dismissive",
    "cynical": "skeptical", "cynicism": "skeptical", "pessimism": "skeptical",
    "pessimistic": "skeptical", "contempt": "dismissive", "scornful": "dismissive",
    "scorn": "dismissive", "indignant": "annoyed", "indignation": "annoyed",
    "exasperated": "frustrated", "exasperation": "frustrated",
    "joy": "delighted", "joyful": "delighted", "happiness": "satisfied",
    "happy": "satisfied", "nostalgia": "dreamy", "nostalgic": "dreamy",
    "cautious": "skeptical", "caution": "skeptical", "wary": "skeptical",
    "thoughtful": "curious", "pensive": "curious", "interest": "intrigued",
    "interested": "intrigued", "surprise": "alarmed", "surprised": "alarmed",
    "serene": "calm", "serenity": "calm", "peaceful": "calm", "peace": "calm",
    "zen": "calm", "compassion": "warm", "compassionate": "warm",
    "concern": "alarmed", "concerned": "alarmed", "worried": "alarmed",
    "worry": "alarmed", "resignation": "resigned", "determination": "confident",
    "conviction": "confident", "convinced": "confident", "firm": "confident",
    "empathy": "warm", "empathetic": "warm", "sympathy": "warm",
    "sympathetic": "warm", "agreement": "gracious", "agreeable": "gracious",
    "thoughtfulness": "curious", "reflective": "dreamy", "reflection": "dreamy",
    "contemplative": "dreamy", "contemplation": "dreamy",
}


def normalize_mood(mood: str | None) -> str:
    word = (mood or "neutral").strip().lower().strip(".,!\"'")
    return MOOD_ALIASES.get(word, word)


def mood_heat(mood: str | None) -> int:
    if not mood:
        return 0
    return MOOD_HEAT.get(mood.strip().lower(), 0)


def strip_name_prefix(text: str, names: list[str]) -> str:
    """Small models sometimes echo the transcript format ("Maya: …")."""
    pattern = r"^(?:(?:" + "|".join(re.escape(n) for n in names) + r")\s*:\s*)+"
    return re.sub(pattern, "", text.strip(), flags=re.IGNORECASE)


# ------------------------------------------------------------- persona store

def _load_custom() -> dict:
    if CUSTOM_FILE.exists():
        try:
            return json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"overrides": {}, "custom": []}


def _save_custom(data: dict) -> None:
    CUSTOM_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def all_personas() -> dict[str, dict]:
    """Builtin YAML personas + user prompt overrides + user-created personas."""
    store = _load_custom()
    out: dict[str, dict] = {}
    for key, p in load_personas(PERSONA_FILE).items():
        d = {
            "key": key, "name": p.name, "emoji": p.emoji, "color": p.color,
            "model": p.model, "system_prompt": p.system_prompt, "builtin": True,
        }
        ov = store["overrides"].get(key, {})
        d.update({k: v for k, v in ov.items() if k in ("system_prompt", "model")})
        out[key] = d
    for i, c in enumerate(store["custom"]):
        c = dict(c)
        c.setdefault("emoji", "🎭")
        c.setdefault("color", PALETTE[(4 + i) % len(PALETTE)])
        c["builtin"] = False
        out[c["key"]] = c
    return out


def persona_obj(d: dict) -> Persona:
    prompt = d["system_prompt"].strip()
    if "never break character" not in prompt.lower():
        prompt += STAY_IN_CHARACTER
    return Persona(
        key=d["key"], name=d["name"], emoji=d["emoji"],
        color=d["color"], model=d["model"], system_prompt=prompt,
    )


# ---------------------------------------------------------------- setup state

class SetupManager:
    """Runs the verification/auto-fix sequence; UI polls status()."""

    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.phase = "idle"  # idle | running | ok | failed
        self.requirements: list[str] = []
        self._task: asyncio.Task | None = None
        self._ollama_proc: subprocess.Popen | None = None

    def status(self) -> dict:
        return {
            "phase": self.phase,
            "checks": self.checks,
            "requirements": self.requirements,
        }

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self.phase = "running"
        self.requirements = []
        self.checks = [
            {"id": "ollama-bin", "label": "Ollama installed", "status": "pending", "detail": ""},
            {"id": "ollama-srv", "label": "Ollama server running", "status": "pending", "detail": ""},
            {"id": "models", "label": "Models downloaded (D: drive)", "status": "pending", "detail": ""},
            {"id": "warm", "label": "Models loaded into memory", "status": "pending", "detail": ""},
        ]
        self._task = asyncio.get_event_loop().create_task(self._run())

    def _check(self, cid: str) -> dict:
        return next(c for c in self.checks if c["id"] == cid)

    def _fail(self, cid: str, detail: str, requirements: list[str]) -> None:
        self._check(cid)["status"] = "fail"
        self._check(cid)["detail"] = detail
        self.requirements = requirements
        self.phase = "failed"

    async def _run(self) -> None:
        try:
            # 1. ollama binary
            c = self._check("ollama-bin")
            c["status"] = "running"
            exe = shutil.which("ollama")
            if not exe:
                self._fail(
                    "ollama-bin", "ollama.exe not found on PATH",
                    ["Install Ollama from https://ollama.com/download and reopen the app."],
                )
                return
            c["status"] = "ok"
            c["detail"] = exe

            # 2. server running (auto-start if not)
            c = self._check("ollama-srv")
            c["status"] = "running"
            if not await ollama_client.is_available():
                c["detail"] = "starting ollama serve…"
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                self._ollama_proc = subprocess.Popen(
                    ["ollama", "serve"], creationflags=flags,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if await ollama_client.is_available():
                        break
                else:
                    self._fail(
                        "ollama-srv", "server did not come up on :11434",
                        ["Ollama is installed but its server won't start.",
                         "Try running `ollama serve` in a terminal to see the error, then press Retry."],
                    )
                    return
            c["status"] = "ok"
            c["detail"] = OLLAMA_HOST

            # 3. models present, pull missing (auto)
            c = self._check("models")
            c["status"] = "running"
            needed = sorted({p["model"] for p in all_personas().values()})
            have = await installed_models()
            missing = [m for m in needed if m not in have]
            for model in missing:
                ok = await pull_model(model, lambda d: c.__setitem__("detail", d))
                if not ok:
                    self._fail(
                        "models", f"failed to download {model}",
                        [f"Model `{model}` could not be downloaded.",
                         "Check your internet connection and free space on D:, then press Retry."],
                    )
                    return
            c["status"] = "ok"
            c["detail"] = ", ".join(needed)

            # 4. warm the models so the first reply is instant
            c = self._check("warm")
            c["status"] = "running"
            for model in needed:
                c["detail"] = f"loading {model}…"
                if not await warm_model(model):
                    self._fail(
                        "warm", f"{model} failed to load",
                        [f"Model `{model}` failed to load. It may not fit in RAM.",
                         "Close other heavy apps and press Retry."],
                    )
                    return
            c["status"] = "ok"
            c["detail"] = "ready"
            self.phase = "ok"
        except Exception as e:  # keep the UI informative, never a dead spinner
            for chk in self.checks:
                if chk["status"] == "running":
                    chk["status"] = "fail"
                    chk["detail"] = str(e)
            self.requirements = [f"Unexpected error: {e}", "Press Retry to run the checks again."]
            self.phase = "failed"


async def installed_models() -> dict[str, str]:
    """name -> human size for everything Ollama has locally."""
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{OLLAMA_HOST}/api/tags")
        out = {}
        for m in r.json().get("models", []):
            gb = m.get("size", 0) / 1e9
            out[m["name"]] = f"{gb:.1f} GB" if gb >= 1 else f"{m.get('size',0)/1e6:.0f} MB"
        return out


async def pull_model(model: str, on_progress) -> bool:
    """Pull via the REST API so we get clean progress JSON."""
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", f"{OLLAMA_HOST}/api/pull",
                json={"name": model, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        on_progress(data["error"])
                        return False
                    total, done = data.get("total"), data.get("completed")
                    if total and done:
                        on_progress(f"downloading {model} — {int(done*100/total)}%")
                    else:
                        on_progress(f"{model}: {data.get('status','')}")
        return True
    except httpx.HTTPError as e:
        on_progress(f"{model}: {e}")
        return False


async def warm_model(model: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            await client.post(f"{OLLAMA_HOST}/api/chat", json={
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False, "keep_alive": "2h",
                "options": {"num_predict": 1},
            })
        return True
    except httpx.HTTPError:
        return False


SETUP = SetupManager()

# One background pull at a time for the "Add persona" flow.
PULL_STATE = {"model": None, "status": "idle", "detail": "", "ok": False}


async def _bg_pull(model: str) -> None:
    PULL_STATE.update(model=model, status="running", detail="starting…", ok=False)
    ok = await pull_model(model, lambda d: PULL_STATE.__setitem__("detail", d))
    if ok:
        PULL_STATE["detail"] = f"loading {model} into memory…"
        ok = await warm_model(model)
    PULL_STATE.update(status="done" if ok else "error", ok=ok)


# ------------------------------------------------------------------- chats

def _chat_path(chat_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", chat_id)
    return CHATS_DIR / f"{safe}.json"


def list_chats() -> list[dict]:
    out = []
    for p in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "id": data["id"], "topic": data["topic"],
                "created": data["created"],
                "participants": data["participants"],
                "count": len(data.get("messages", [])),
                "mode": data.get("mode", "debate"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    out.sort(key=lambda c: c["created"], reverse=True)
    return out


# ------------------------------------------------------------ debate loop

CLOSING_PROMPT = (
    "The debate is wrapping up now. Give your closing statement in 1-2 "
    "sentences: your final position on the topic, honestly conceding any "
    "point from the others you now accept. Stay completely in character."
)

# Discuss mode: a casual group chat, not a formal debate.
CHAT_STYLE = (
    "\nRight now you're all hanging out in a casual group chat, not a formal"
    " debate. Text like a real person: ONE short line most of the time, under"
    " 20 words. Sometimes reply with just a quick reaction or an action in"
    " asterisks like *sips tea* or *raises eyebrow*. And sometimes — a few"
    " times a conversation — just say ONE or TWO words and stop, nothing"
    " more: 'lol no.' 'facts.' 'wait what.' 'same tbh.' Real texting has"
    " those too; don't turn every single reply into a mini-essay. Emojis are"
    " fine when they fit, never forced. React directly to the last message —"
    " agree, tease, doubt, push back. Every so often throw a direct question"
    " at another member, like 'do you agree, {other}?'. Together, work"
    " toward an actual answer."
)

CHAT_CLOSING = (
    "Time to wrap it up. Give your final verdict on the question in ONE "
    "short line, in character. An emoji is fine if it fits."
)

# Solo mode: it's you against one persona, and the persona is built to
# always take the other side.
SOLO_STYLE = (
    "\nRight now it's just the two of you talking directly, one-on-one, like"
    " texting a close friend. Whatever they say, you push back — play devil's"
    " advocate, poke holes, ask 'wait, how do you figure that', bring up the"
    " downside they're not mentioning. You almost never just agree outright."
    " But it's warm pushback, not hostility — talk like a bro: casual,"
    " a little teasing, on their side even while you're arguing with them"
    " ('nah bro hear me out though...', '*tilts head* okay but what about...',"
    " 'i mean i love you but that's not it chief'). ONE short line most of the"
    " time, under 20 words. And every so often — not every time — just fire"
    " back ONE or TWO words and stop: 'nah.' 'doubt it.' 'lol no.' 'wait,"
    " what.' Real texting isn't always a full sentence. Actions in asterisks"
    " and emoji are fine, never forced. Talk directly to them, you don't know"
    " their name so don't invent one."
)


def _build_solo_messages(
    persona: Persona, transcript: list[tuple[str, str]]
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": persona.system_prompt}]
    for speaker, text in transcript:
        role = "assistant" if speaker == persona.name else "user"
        messages.append({"role": role, "content": text})
    return messages


def _build_chat_messages(
    persona: Persona, topic: str, transcript: list[tuple[str, str]]
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": persona.system_prompt}]
    messages.append({
        "role": "user",
        "content": (
            f"Someone just dropped this in the group chat: {topic}\n"
            "Jump in like a group chat member. Keep it short and alive."
        ),
    })
    for speaker, text in transcript:
        role = "assistant" if speaker == persona.name else "user"
        messages.append({"role": role, "content": f"{speaker}: {text}"})
    return messages


async def run_web_debate(topic: str, fighters: list[Persona], rounds: int,
                         mode: str = "debate"):
    """Round-robin debate/discussion + a closing round, yielding dict events.

    Like swarm_kit.orchestrator.run_debate but with a final closing phase so
    the fight actually reaches a conclusion, and an optional casual chat mode.
    """
    chatty = mode == "chat"
    options = {"num_predict": 80} if chatty else None
    transcript: list[tuple[str, str]] = []
    for round_idx in range(rounds + 1):
        closing = round_idx == rounds
        if closing:
            yield {"type": "phase", "label": "The verdict" if chatty else "Closing arguments"}
        for p in fighters:
            yield {"type": "start", "persona": p.key}
            full_text = ""
            mood = "neutral"
            try:
                if chatty:
                    messages = _build_chat_messages(p, topic, transcript)
                else:
                    messages = _build_messages(p, topic, transcript)
                if closing:
                    messages.append({
                        "role": "user",
                        "content": CHAT_CLOSING if chatty else CLOSING_PROMPT,
                    })
                async for chunk in ollama_client.stream_chat(p.model, messages,
                                                             options=options):
                    full_text += chunk
                mood = await fetch_mood(p, full_text.strip())
            except ollama_client.OllamaError as e:
                full_text = full_text or f"[error: {e}]"
                mood = "confused"
            transcript.append((p.name, full_text.strip()))
            yield {"type": "end", "persona": p.key, "text": full_text.strip(),
                   "mood": mood, "closing": closing}


# ------------------------------------------------------------------ handlers

async def h_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(Path(__file__).parent / "index.html")


async def h_setup_status(request: web.Request) -> web.Response:
    return web.json_response(SETUP.status())


async def h_setup_run(request: web.Request) -> web.Response:
    SETUP.start()
    return web.json_response({"ok": True})


async def h_personas(request: web.Request) -> web.Response:
    return web.json_response(list(all_personas().values()))


async def h_persona_save(request: web.Request) -> web.Response:
    body = await request.json()
    store = _load_custom()
    key = body.get("key") or ""
    personas = all_personas()

    if key and key in personas and personas[key]["builtin"]:
        # builtins: only prompt/model can be changed
        ov = store["overrides"].setdefault(key, {})
        if body.get("system_prompt"):
            ov["system_prompt"] = body["system_prompt"]
        if body.get("model"):
            ov["model"] = body["model"]
    else:
        name = (body.get("name") or "").strip()
        model = (body.get("model") or "").strip()
        prompt = (body.get("system_prompt") or "").strip()
        if not (name and model and prompt):
            raise web.HTTPBadRequest(text="name, model and system_prompt required")
        if not key:
            key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"p{uuid.uuid4().hex[:5]}"
            while key in personas:
                key += "2"
        entry = {
            "key": key, "name": name, "model": model, "system_prompt": prompt,
            "emoji": (body.get("emoji") or "🎭").strip() or "🎭",
        }
        existing = [c for c in store["custom"] if c["key"] == key]
        if existing:
            entry["color"] = existing[0].get("color")
            store["custom"] = [entry if c["key"] == key else c for c in store["custom"]]
        else:
            entry["color"] = PALETTE[(4 + len(store["custom"])) % len(PALETTE)]
            store["custom"].append(entry)
    _save_custom(store)
    return web.json_response({"ok": True, "key": key})


async def h_persona_delete(request: web.Request) -> web.Response:
    key = request.match_info["key"]
    store = _load_custom()
    store["custom"] = [c for c in store["custom"] if c["key"] != key]
    store["overrides"].pop(key, None)  # for builtins this resets to default
    _save_custom(store)
    return web.json_response({"ok": True})


async def h_models(request: web.Request) -> web.Response:
    have = await installed_models()
    out = [{"name": n, "size": s, "installed": True} for n, s in sorted(have.items())]
    for m in MODEL_CATALOG:
        if m["name"] not in have:
            out.append({"name": m["name"], "size": m["size"] + " ↓", "installed": False})
    return web.json_response(out)


async def h_model_pull(request: web.Request) -> web.Response:
    body = await request.json()
    model = (body.get("model") or "").strip()
    if not model:
        raise web.HTTPBadRequest(text="model required")
    if PULL_STATE["status"] == "running":
        return web.json_response({"ok": False, "error": "another download is running"})
    asyncio.get_event_loop().create_task(_bg_pull(model))
    return web.json_response({"ok": True})


async def h_model_pull_status(request: web.Request) -> web.Response:
    return web.json_response(PULL_STATE)


async def h_chats(request: web.Request) -> web.Response:
    return web.json_response(list_chats())


async def h_chat_get(request: web.Request) -> web.Response:
    path = _chat_path(request.match_info["id"])
    if not path.exists():
        raise web.HTTPNotFound()
    return web.json_response(json.loads(path.read_text(encoding="utf-8")))


async def h_chat_delete(request: web.Request) -> web.Response:
    path = _chat_path(request.match_info["id"])
    if path.exists():
        path.unlink()
    return web.json_response({"ok": True})


async def h_debate(request: web.Request) -> web.StreamResponse:
    """SSE stream of one full debate; persists the chat as it goes."""
    topic = request.query.get("topic", "").strip()
    if not topic:
        raise web.HTTPBadRequest(text="topic required")
    keys = [k for k in request.query.get("personas", "").split(",") if k]
    rounds = max(1, min(6, int(request.query.get("rounds", "3"))))
    mode = "chat" if request.query.get("mode") == "chat" else "debate"

    catalog = all_personas()
    keys = [k for k in keys if k in catalog]
    if len(keys) < 2:
        raise web.HTTPBadRequest(text="need at least 2 valid personas")

    # Hand out random human names and let everyone know who's in the ring.
    display = random.sample(NAMES, len(keys))
    fighters: list[Persona] = []
    for i, k in enumerate(keys):
        base = persona_obj(catalog[k])
        others = ", ".join(f"{display[j]} (the {catalog[kk]['name']})"
                           for j, kk in enumerate(keys) if j != i)
        prompt = (
            base.system_prompt
            + f"\nIn this debate your name is {display[i]}. "
              f"You are arguing with: {others}. Address them by name when it feels natural."
        )
        if mode == "chat":
            other = display[(i + 1) % len(display)]
            prompt += CHAT_STYLE.format(other=other)
        fighters.append(dataclasses.replace(base, name=display[i], system_prompt=prompt))

    chat_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    chat = {
        "id": chat_id, "topic": topic, "created": time.time(),
        "participants": keys, "rounds": rounds, "messages": [], "mode": mode,
        "names": {k: display[i] for i, k in enumerate(keys)},
    }

    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)

    async def send(payload: dict) -> None:
        await resp.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))

    by_key = {f.key: f for f in fighters}
    heat = 15.0
    await send({"type": "meta", "chat_id": chat_id, "topic": topic, "mode": mode,
                "personas": [{"key": k, "name": display[i],
                              "role": catalog[k]["name"],
                              "emoji": catalog[k]["emoji"],
                              "color": catalog[k]["color"]}
                             for i, k in enumerate(keys)]})
    try:
        async for ev in run_web_debate(topic, fighters, rounds, mode):
            if ev["type"] in ("phase", "start"):
                await send(ev)
                continue
            mood = normalize_mood(ev["mood"])
            heat = min(100.0, 0.75 * heat + mood_heat(mood) * 11 + 4)
            k = ev["persona"]
            msg = {
                "persona": k,
                "name": by_key[k].name,
                "role": catalog[k]["name"],
                "emoji": catalog[k]["emoji"],
                "color": catalog[k]["color"],
                "text": strip_name_prefix(ev["text"], display),
                "mood": mood,
                "mood_emoji": emoji_for(mood),
                "heat": round(heat),
                "closing": ev.get("closing", False),
            }
            chat["messages"].append(msg)
            _chat_path(chat_id).write_text(json.dumps(chat, indent=2), encoding="utf-8")
            await send({"type": "end", **msg})
        await send({"type": "done", "chat_id": chat_id})
    except (ConnectionResetError, asyncio.CancelledError):
        pass  # user pressed Stop or closed the tab mid-debate
    finally:
        if chat["messages"]:
            _chat_path(chat_id).write_text(json.dumps(chat, indent=2), encoding="utf-8")
    return resp


async def h_solo(request: web.Request) -> web.StreamResponse:
    """SSE: one turn of a solo 1:1 chat — user message in, one persona reply out.

    Unlike /api/debate (which autoplays a whole fight from a single topic),
    this is called once per user message, carrying the running chat_id so
    the transcript and heat persist turn to turn.
    """
    message = request.query.get("message", "").strip()
    persona_key = request.query.get("persona", "").strip()
    chat_id = request.query.get("chat_id", "").strip()
    if not message or not persona_key:
        raise web.HTTPBadRequest(text="message and persona required")

    catalog = all_personas()
    if persona_key not in catalog:
        raise web.HTTPBadRequest(text="unknown persona")

    if chat_id:
        path = _chat_path(chat_id)
        if not path.exists():
            raise web.HTTPNotFound()
        chat = json.loads(path.read_text(encoding="utf-8"))
    else:
        chat_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        display = random.choice(NAMES)
        chat = {
            "id": chat_id, "topic": message[:80], "created": time.time(),
            "participants": [persona_key], "mode": "solo", "messages": [],
            "names": {persona_key: display},
        }

    display = chat["names"][persona_key]
    base = persona_obj(catalog[persona_key])
    opponent = dataclasses.replace(
        base, name=display, system_prompt=base.system_prompt + SOLO_STYLE,
    )

    last_heat = chat["messages"][-1]["heat"] if chat["messages"] else 15
    transcript = [(m["name"], m["text"]) for m in chat["messages"]]
    transcript.append(("You", message))

    user_msg = {
        "persona": "user", "name": "You", "role": "", "emoji": "🙂", "color": "user",
        "text": message, "mood": None, "mood_emoji": None, "heat": last_heat,
        "is_user": True,
    }
    chat["messages"].append(user_msg)

    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)

    async def send(payload: dict) -> None:
        await resp.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))

    await send({"type": "meta", "chat_id": chat_id, "topic": chat["topic"], "mode": "solo",
                "personas": [{"key": persona_key, "name": display,
                              "role": catalog[persona_key]["name"],
                              "emoji": catalog[persona_key]["emoji"],
                              "color": catalog[persona_key]["color"]}]})
    await send({"type": "start", "persona": persona_key})
    full_text = ""
    mood = "neutral"
    try:
        messages = _build_solo_messages(opponent, transcript)
        async for chunk in ollama_client.stream_chat(opponent.model, messages,
                                                      options={"num_predict": 80}):
            full_text += chunk
        mood = await fetch_mood(opponent, full_text.strip())
    except ollama_client.OllamaError as e:
        full_text = full_text or f"[error: {e}]"
        mood = "confused"

    mood = normalize_mood(mood)
    heat = min(100.0, 0.75 * last_heat + mood_heat(mood) * 11 + 4)
    bot_msg = {
        "persona": persona_key, "name": display, "role": catalog[persona_key]["name"],
        "emoji": catalog[persona_key]["emoji"], "color": catalog[persona_key]["color"],
        "text": strip_name_prefix(full_text.strip(), [display]),
        "mood": mood, "mood_emoji": emoji_for(mood), "heat": round(heat),
        "is_user": False,
    }
    chat["messages"].append(bot_msg)
    _chat_path(chat_id).write_text(json.dumps(chat, indent=2), encoding="utf-8")
    await send({"type": "end", **bot_msg})
    await send({"type": "done", "chat_id": chat_id})
    return resp


def make_app() -> web.Application:
    app = web.Application()
    app.add_routes([
        web.get("/", h_index),
        web.get("/api/setup/status", h_setup_status),
        web.post("/api/setup/run", h_setup_run),
        web.get("/api/personas", h_personas),
        web.post("/api/personas", h_persona_save),
        web.delete("/api/personas/{key}", h_persona_delete),
        web.get("/api/models", h_models),
        web.post("/api/models/pull", h_model_pull),
        web.get("/api/models/pull/status", h_model_pull_status),
        web.get("/api/chats", h_chats),
        web.get("/api/chats/{id}", h_chat_get),
        web.delete("/api/chats/{id}", h_chat_delete),
        web.get("/api/debate", h_debate),
        web.get("/api/solo", h_solo),
    ])
    return app


def run(port: int = 8765) -> None:
    web.run_app(make_app(), host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    run()
