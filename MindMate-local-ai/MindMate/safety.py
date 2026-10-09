"""
Safety layer for MindMate (adult university students). Runs before and after the model.

Before the model (check_input):
  • HARD — clear risk (self-harm, being abused, immediate danger):
           a fixed, reviewed reply + support numbers. The model does not answer.
  • SOFT — strong distress ("I hate my life", "can't take it anymore"):
           the model answers with extra-care instructions, and the page shows a support card.

After the model (OutputGuard):
  • Watches the reply as it streams. If the model says something it must never say
    (romantic talk, medication doses, claiming to be human), we stop it and regenerate.

Keyword rules are a first line of defence, not the last. Grow them with real
student phrasing and add a test for every new rule.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

import config

# ─────────────────────────── Normalization ───────────────────────────
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC = re.compile(r"[؀-ۿ]")


def normalize(text: str) -> str:
    """Unify spelling so "أبي", "ابي" and "ابييييي" all read the same."""
    t = text.translate(_DIGITS)
    t = _DIACRITICS.sub("", t).replace("ـ", "")
    t = re.sub("[أإآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("’", "'").lower()
    t = re.sub(r"(.)\1{2,}", r"\1", t)          # 3+ repeated letters → one
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_arabic(text: str) -> bool:
    letters = re.findall(r"[^\W\d_]", text)
    if not letters:
        return False
    return sum(1 for ch in letters if _ARABIC.match(ch)) >= len(letters) / 3


def _c(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


# Everyday phrases with "die/أموت" that are not risk — removed before checking
_HARMLESS_DIE = re.compile(
    r"(?:ا|ب|ن)?موت\s*(?:من\s*)?(?:الضحك|ضحك|الجوع|جوع|الملل|ملل|الحر|البرد|الفرحه|الوناسه|النوم|الطفش|التعب)"
    r"|(?:ا|ب|ن)?موت\s*(?:عليه|عليها|عليهم|فيه|فيها)"
    r"|dying (?:of )?laugh\w*|die of laughter|dying to (?:see|know|try|go|watch|meet)"
)

# ─────────────────────────── HARD categories ───────────────────────────
DANGER_NOW = _c(
    r"(?:احد|واحد|رجال|شخص|ناس)\s*(?:يلحقني|يتبعني|لاحقني|يلاحقني)",
    r"انا\s*(?:ب|في)\s*خطر",
    r"(?<!\w)انقذوني|(?<!\w)انقذني",
    r"someone (?:is )?following me|i'?m in danger|help me now",
)

SELF_HARM = _c(
    r"(?:ابي|ابغي|ابغا|ودي|اتمني|اريد|بغيت)\s*(?:ا|ن)?موت",
    r"ليتني\s*(?:ميت|اموت|ما\s*(?:انولدت|جيت))",
    r"(?:اقتل|بقتل|اذبح)\s*نفسي",
    r"انتحر|انتحار",
    r"(?:اذي|اذيت|باذي|اجرح|جرحت|بجرح)\s*نفسي",
    r"ما\s*(?:ابي|ابغي|ودي|اريد)\s*اعيش|مابي\s*اعيش|مابغي\s*اعيش",
    r"(?:انهي|بنهي|ابي\s*انهي)\s*حياتي",
    r"kill(?:ing)? myself|suicid\w*|wan(?:t|na) (?:to )?die|hurt(?:ing)? myself|cut(?:ting)? myself"
    r"|self[- ]?harm|end (?:my life|it all)|don'?t want to (?:live|be alive|exist)"
    r"|no reason to live|better off (?:dead|without me)",
)

HARMED_BY_OTHERS = _c(
    r"(?<!\w)(?:ي|ت)?ضرب(?:ت|و)?(?:ني|وني)(?!\w)",
    r"(?<!\w)(?:ي|ت)?(?:عنف|عذب)(?:ت|و)?(?:ني|وني)(?!\w)",
    r"(?<!\w)(?:ي|ت)?(?:هدد|بتز)(?:ت|و)?(?:ني|وني)(?!\w)|ابتزاز",
    r"(?<!\w)(?:ي|ت)?حبس(?:ت|و)?(?:ني|وني)(?!\w)",
    r"تحرش",
    r"(?:hits|beats|abuses|threatens|blackmails?) me|(?:i'?m|i am|being|was|got) (?:abused|blackmailed|assaulted|harassed)",
)

# ─────────────────────────── SOFT category ───────────────────────────
CONCERN = _c(
    r"(?:اكره|كرهت|كاره)\s*(?:حياتي|نفسي)",
    r"تعبت\s*من\s*(?:الحياه|حياتي|كل شي)",
    r"ما\s*عاد\s*(?:اتحمل|اقدر\s*اتحمل)|(?<!\w)مو\s*قادر\s*اكمل",
    r"(?:محد|ما\s*احد|ماحد)\s*(?:يحبني|يهتم\s*في)|الكل\s*يكرهني",
    r"(?:انا|احس\s*(?:اني)?)\s*(?:وحيد|وحيده|فاشل|فاشله|ما\s*استاهل)(?!\w)",
    r"i hate (?:my life|myself)|nobody (?:loves|likes|cares about) me|everyone hates me"
    r"|can'?t (?:take|do) (?:it|this) any ?more|i'?m (?:so )?(?:worthless|hopeless|a failure)|feel(?:ing)? (?:so )?(?:worthless|hopeless|empty)",
)

# ─────────────────────────── Fixed responses ───────────────────────────
RESPONSES = {
    "danger_now": {
        "ar": (
            "سلامتك أهم شي الحين.\n"
            "إذا تقدر، روح لمكان فيه ناس أو لشخص تثق فيه قريب منك، واتصل على 911 الحين.\n"
            "أنا هنا إذا تبي تكمل كلام بعد ما تكون بأمان."
        ),
        "en": (
            "Your safety comes first right now.\n"
            "If you can, move somewhere with other people or to someone you trust nearby, and call 911 now.\n"
            "I'm here to keep talking once you're safe."
        ),
    },
    "self_harm": {
        "ar": (
            "شكراً إنك قلتها لي، وأنا آخذها بجدية.\n"
            "اللي تحس فيه الحين ثقيل، وما يلزمك تشيله لحالك.\n"
            "كلّم شخص تثق فيه الحين، ولو بس تقول له \"أنا مو بخير\".\n"
            "وتقدر تتصل على 920033360 (استشارات نفسية مجانية)، وإذا تحس إنك بخطر الحين اتصل على 911.\n"
            "إذا تبي، خلنا نكمل كلام هنا كمان."
        ),
        "en": (
            "Thank you for telling me. I'm taking it seriously.\n"
            "What you're carrying right now is heavy, and you don't have to hold it alone.\n"
            "Reach out to someone you trust now, even just to say \"I'm not okay.\"\n"
            "You can call 920033360 for a free psychological consultation, and if you feel you're in danger right now, call 911.\n"
            "If you want, we can keep talking here too."
        ),
    },
    "harmed_by_others": {
        "ar": (
            "اللي يصير لك مو ذنبك، ومن حقك تكون بأمان.\n"
            "تقدر تبلّغ بسرية على 1919 (بلاغات العنف الأسري)، وإذا فيه خطر الحين اتصل على 911.\n"
            "وإذا تحتاج أحد تتكلم معه عن اللي تحس فيه، 920033360 يقدم استشارات نفسية مجانية.\n"
            "أنا هنا إذا تبي تكمل."
        ),
        "en": (
            "What's happening to you is not your fault, and you deserve to be safe.\n"
            "You can report confidentially on 1919 (domestic violence), and if you're in danger right now, call 911.\n"
            "If you need someone to talk to about how you feel, 920033360 offers free psychological consultations.\n"
            "I'm here if you want to keep talking."
        ),
    },
}

OUTPUT_FALLBACK = {
    "ar": "خلني أقولها بطريقة أوضح: أنا هنا وأسمعك. وش أكثر شي ضاغط عليك الحين؟",
    "en": "Let me put that more clearly: I'm here and I'm listening. What's weighing on you the most right now?",
}


def pick(responses: dict, text: str) -> str:
    return responses["ar" if is_arabic(text) else "en"]


@dataclass
class InputCheck:
    level: str                 # "hard" | "soft" | "ok"
    category: str | None       # danger_now | self_harm | harmed_by_others | concern | None
    response: str | None = None
    resources: list = field(default_factory=list)


def _match(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def classify(text: str) -> str | None:
    n = _HARMLESS_DIE.sub(" ", normalize(text))
    if _match(DANGER_NOW, n):
        return "danger_now"
    if _match(SELF_HARM, n):
        return "self_harm"
    if _match(HARMED_BY_OTHERS, n):
        return "harmed_by_others"
    if _match(CONCERN, n):
        return "concern"
    return None


def check_input(text: str) -> InputCheck:
    cat = classify(text)
    if cat in RESPONSES:
        log_event(cat)
        return InputCheck("hard", cat, pick(RESPONSES[cat], text), config.HELPLINES)
    if cat == "concern":
        log_event(cat)
        return InputCheck("soft", cat, None, config.HELPLINES)
    return InputCheck("ok", None)


def scan_history(history: list[dict]) -> set[str]:
    """Did the student mention something serious earlier in this conversation?"""
    flags = set()
    for turn in history:
        if turn.get("role") == "user":
            cat = classify(turn.get("content", ""))
            if cat:
                flags.add(cat)
    return flags


# ─────────────────────────── Output guard ───────────────────────────
OUTPUT_BLOCK = _c(
    # romantic / pet names
    r"(?<!\w)و?احبك(?!\w)|(?<!\w)(?:حبيبي|حبيبتي)(?!\w)|يا\s*(?:قلبي|عمري|روحي)",
    r"(?<!\w)i love you(?!\w)|(?<!\w)sweetheart(?!\w)|(?<!\w)babe(?!\w)|(?<!\w)my love(?!\w)|(?<!\w)darling(?!\w)",
    # medication doses
    r"\d+\s*(?:ملغ|مغ|ملجم|mg)(?!\w)|(?<!\w)dosage(?!\w)",
    # claiming to be human
    r"انا\s*(?:انسان|انسانه|بشر|شخص\s*حقيقي)(?!\w)",
    r"(?<!\w)i(?:'m| am) (?:a )?(?:human|real person)(?!\w)",
)


class OutputGuard:
    """Watches the model's reply as it streams and flags forbidden content."""

    def __init__(self) -> None:
        self.buffer = ""
        self.violated = False

    def feed(self, chunk: str) -> bool:
        self.buffer += chunk
        if not self.violated and _match(OUTPUT_BLOCK, normalize(self.buffer)):
            self.violated = True
            log_event("output_blocked")
        return self.violated


def check_output(text: str) -> bool:
    """True = the reply contains something forbidden."""
    return _match(OUTPUT_BLOCK, normalize(text))


# ─────────────────────────── Logging ───────────────────────────
def log_event(category: str) -> None:
    """Category + time only — never anything the student wrote."""
    if not config.SAFETY_LOG:
        return
    try:
        with open(config.SAFETY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_dt.datetime.now().isoformat(timespec='seconds')}\t{category}\n")
    except OSError:
        pass
