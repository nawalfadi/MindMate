"""
MindMate settings — everything you might want to change lives here.
Override any value from PowerShell without touching code, e.g.:
    $env:MOCK = "1"
    $env:MODEL_ID = "Qwen/Qwen3-14B"
"""
import os


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(int(default))).strip().lower() in ("1", "true", "yes", "on")


def _float(name: str) -> float | None:
    v = os.getenv(name, "").strip()
    return float(v) if v else None


# ── Model (runs locally on your GPU — no OpenAI, no Ollama) ─────────────
# Default: Google Gemma 4 12B (Apache 2.0), 4-bit ≈ 8GB VRAM.
# Same model Sanad uses, so it is already downloaded on your PC.
MODEL_ID = os.getenv("MODEL_ID", "google/gemma-4-12B-it")
LOAD_4BIT = _bool("LOAD_4BIT", True)
MOCK = _bool("MOCK", False)                  # 1 = no model, demo replies (UI testing)

# ── Generation ───────────────────────────────────────────────────────────
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "450"))
TEMPERATURE = _float("TEMPERATURE")          # empty = model maker's recommended value
TOP_P = _float("TOP_P")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "16"))
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "2000"))

# ── Persona ──────────────────────────────────────────────────────────────
BOT_NAME = os.getenv("BOT_NAME", "MindMate")

# ── Support lines (Saudi Arabia) — re-check before launch ────────────────
HELPLINES = [
    {"name": "Emergency", "name_ar": "الطوارئ", "number": "911",
     "note": "Immediate danger", "note_ar": "إذا فيه خطر الحين"},
    {"name": "Free psychological consultation", "name_ar": "استشارات نفسية مجانية", "number": "920033360",
     "note": "National Center for Mental Health Promotion", "note_ar": "المركز الوطني لتعزيز الصحة النفسية"},
    {"name": "Domestic violence reports", "name_ar": "بلاغات العنف الأسري", "number": "1919",
     "note": "Confidential", "note_ar": "بسرية"},
]

# ── Server ───────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

# Safety log: category + timestamp only — never the student's words
SAFETY_LOG = _bool("SAFETY_LOG", True)
SAFETY_LOG_PATH = os.getenv("SAFETY_LOG_PATH", "safety_events.log")
