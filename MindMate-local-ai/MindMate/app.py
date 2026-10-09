"""
MindMate — Flask app running a local LLM (no OpenAI, no Ollama).

    GET  /             the website
    POST /chat         send a message → reply streams word by word (Server-Sent Events)
                       (send without "Accept: text/event-stream" to get one JSON {"reply": ...})
    GET  /api/health   server + model status

Run:  python app.py
"""
from __future__ import annotations

import json
import threading

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

import config
import safety
from engine import get_engine
from prompts import RETRY_NOTE, build_instructions

app = Flask(__name__)
engine = get_engine()
_load_lock = threading.Lock()

ALLOWED_EMOTIONS = {
    "Joy", "Sadness", "Anger", "Fear", "Disgust",
    "Anxiety", "Envy", "Embarrassment", "Ennui",
}


def ensure_engine() -> None:
    if not engine.ready:
        with _load_lock:
            if not engine.ready:
                engine.load()


# ── Routes ───────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html", helplines=config.HELPLINES, bot_name=config.BOT_NAME)


@app.get("/api/health")
def health():
    return jsonify(status="ok", bot=config.BOT_NAME, model=engine.name, mock=config.MOCK, ready=engine.ready)


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    parsed, error = parse_request(data)
    if error:
        return jsonify(error=error), 400

    ensure_engine()
    events = chat_events(*parsed)

    if "text/event-stream" in request.headers.get("Accept", ""):
        return Response(
            stream_with_context(events),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Simple JSON mode (for scripts or the old frontend)
    reply, extra = "", {}
    for raw in events:
        ev = json.loads(raw[len("data: "):])
        if ev["type"] == "token":
            reply += ev["text"]
        elif ev["type"] == "replace":
            reply = ev["text"]
        elif ev["type"] == "safety":
            extra = {"safety": ev["category"], "resources": ev["resources"]}
        elif ev["type"] == "error":
            reply = ev["text"]
    return jsonify(reply=reply.strip(), **extra)


# ── Request validation ───────────────────────────────────────────────────
def parse_request(data: dict):
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return None, "Please tell me how you're feeling."
    message = message.strip()
    if len(message) > config.MAX_MESSAGE_CHARS:
        return None, f"Message is too long (max {config.MAX_MESSAGE_CHARS} characters)."

    emotion = data.get("emotion", "")
    emotion = emotion.strip() if isinstance(emotion, str) else ""
    if emotion not in ALLOWED_EMOTIONS:
        emotion = ""

    raw_history = data.get("history", [])
    if not isinstance(raw_history, list) or len(raw_history) > 200:
        return None, "Invalid history."
    history = []
    for turn in raw_history[-config.MAX_HISTORY_TURNS:]:
        # only user/assistant — the browser can never inject a "system" message
        if not isinstance(turn, dict) or turn.get("role") not in ("user", "assistant"):
            return None, "Invalid history."
        content = turn.get("content", "")
        if not isinstance(content, str) or len(content) > 8000:
            return None, "Invalid history."
        history.append({"role": turn["role"], "content": content})

    return (message, emotion, history), None


# ── Chat logic ───────────────────────────────────────────────────────────
def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def chat_events(message: str, emotion: str, history: list[dict]):
    check = safety.check_input(message)

    # Clear risk → fixed, reviewed reply. The model does not answer.
    if check.level == "hard":
        yield sse({"type": "safety", "category": check.category, "resources": check.resources})
        yield sse({"type": "token", "text": check.response})
        yield sse({"type": "done"})
        return

    flags = safety.scan_history(history)
    if check.level == "soft":
        flags.add(check.category)
        yield sse({"type": "safety", "category": check.category, "resources": check.resources})

    messages = (
        [{"role": "system", "content": build_instructions(emotion, flags)}]
        + history
        + [{"role": "user", "content": message}]
    )

    try:
        violated = yield from stream_guarded(messages)
        if violated:
            # The model said something forbidden → wipe it and regenerate once with a warning
            yield sse({"type": "replace", "text": ""})
            retry = [{"role": "system", "content": messages[0]["content"] + RETRY_NOTE}] + messages[1:]
            violated = yield from stream_guarded(retry)
            if violated:
                yield sse({"type": "replace", "text": safety.pick(safety.OUTPUT_FALLBACK, message)})
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] generation failed: {exc!r}")
        yield sse({"type": "error", "text": "Sorry, something went wrong. Please try again."})
        return

    yield sse({"type": "done"})


def stream_guarded(messages: list[dict]):
    """Streams the reply; stops as soon as something forbidden appears. Returns True if blocked."""
    guard = safety.OutputGuard()
    stop = threading.Event()
    gen = engine.stream(messages, stop)
    try:
        for piece in gen:
            if guard.feed(piece):
                stop.set()
                break
            yield sse({"type": "token", "text": piece})
    finally:
        stop.set()
        gen.close()          # frees the GPU before a retry
    return guard.violated


if __name__ == "__main__":
    ensure_engine()          # load the model once, before the first visitor
    print(f"\n>>> MindMate: http://{config.HOST}:{config.PORT}   (model: {engine.name})\n")
    # debug=False: the Flask debugger allows running code from the browser — never expose it.
    # use_reloader=False: otherwise Flask starts twice and loads the model twice.
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True, use_reloader=False)
