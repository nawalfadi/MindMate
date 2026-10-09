"""
المحرك — هنا الموديل يشتغل مباشرة داخل كودنا (بدون Ollama أو أي برنامج وسيط).

    MockEngine          رد تجريبي سريع — لتجربة الواجهة بدون GPU أو تحميل موديل
    TransformersEngine  الموديل الحقيقي على كرت الشاشة عن طريق Hugging Face transformers
"""
from __future__ import annotations

import re
import threading
import time
from typing import Iterable, Iterator

import config

# إعدادات التوليد اللي تنصح فيها كل شركة لموديلها (للوضع بدون "تفكير")
PRESETS = {
    "gemma": {"temperature": 0.9, "top_p": 0.95, "top_k": 64, "repetition_penalty": 1.0},
    "qwen": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "repetition_penalty": 1.05},
    "default": {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "repetition_penalty": 1.05},
}


def preset_for(model_id: str) -> dict:
    mid = model_id.lower()
    p = dict(next((v for k, v in PRESETS.items() if k in mid), PRESETS["default"]))
    if config.TEMPERATURE is not None:
        p["temperature"] = config.TEMPERATURE
    if config.TOP_P is not None:
        p["top_p"] = config.TOP_P
    return p


class MockEngine:
    name = "mock"
    ready = False

    def load(self) -> None:
        self.ready = True
        print("MOCK mode - no model, demo replies only.")

    def stream(self, messages: list[dict], stop: threading.Event) -> Iterator[str]:
        reply = (
            f"Hi, I'm {config.BOT_NAME}. This is a demo reply (MOCK mode) so you can check the page works. "
            "Start the real model and I'll answer properly. How are you feeling today?"
        )
        for word in reply.split(" "):
            if stop.is_set():
                return
            time.sleep(0.04)
            yield word + " "

    def complete(self, messages: list[dict]) -> str:
        return "".join(self.stream(messages, threading.Event())).strip()


class TransformersEngine:
    def __init__(self, model_id: str, load_4bit: bool = True) -> None:
        self.name = model_id
        self.load_4bit = load_4bit
        self.ready = False
        self.gen = preset_for(model_id)
        self._lock = threading.Lock()   # كرت شاشة واحد = رد واحد في نفس الوقت

    # ── تحميل الموديل ─────────────────────────────────────
    def load(self) -> None:
        import torch
        import transformers as tf

        self.torch = torch
        cuda = torch.cuda.is_available()
        if cuda:
            free, total = torch.cuda.mem_get_info()
            print(f"[GPU] {torch.cuda.get_device_name(0)}  ({free / 2**30:.1f} / {total / 2**30:.1f} GB free)")
        else:
            print("[!] CUDA not found - running on CPU (very slow). See README > troubleshooting.")

        kwargs: dict = {"dtype": torch.bfloat16 if cuda else torch.float32, "device_map": "cuda" if cuda else "cpu"}
        if self.load_4bit and cuda:
            kwargs["quantization_config"] = tf.BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
            )

        print(f"[..] Loading {self.name}  (4-bit: {self.load_4bit and cuda}) - first run downloads the weights")
        self.tok = _load_tokenizer(tf, self.name)
        self.model = _load_model(tf, self.name, kwargs)
        self.model.eval()
        self.ready = True
        if cuda:
            print(f"[OK] Model ready - using {torch.cuda.memory_allocated() / 2**30:.1f} GB VRAM")
        else:
            print("[OK] Model ready")

    # ── تجهيز البرومبت ───────────────────────────────────
    def _encode(self, messages: list[dict]):
        def render(msgs):
            return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)

        try:
            text = render(messages)
        except Exception:
            # بعض الموديلات ما تقبل role=system → ندمجه مع أول رسالة
            merged = [dict(m) for m in messages if m["role"] != "system"]
            system = "\n".join(m["content"] for m in messages if m["role"] == "system")
            if merged and merged[0]["role"] == "user":
                merged[0]["content"] = f"{system}\n\n{merged[0]['content']}"
            text = render(merged)
        return self.tok(text, return_tensors="pt", add_special_tokens=False).to(self.model.device)

    # ── التوليد (streaming) ──────────────────────────────
    def stream(self, messages: list[dict], stop: threading.Event) -> Iterator[str]:
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        torch = self.torch

        class _StopOnEvent(StoppingCriteria):
            def __call__(self, input_ids, scores, **kw):
                return torch.full((input_ids.shape[0],), stop.is_set(), dtype=torch.bool, device=input_ids.device)

        with self._lock:
            inputs = self._encode(messages)
            # نخلي الرموز الخاصة تطلع عشان ننظفها بأنفسنا (تفكير الموديل وعلامات نهاية الدور)
            streamer = TextIteratorStreamer(self.tok, skip_prompt=True, skip_special_tokens=False, timeout=300)
            gen_kwargs = dict(
                **inputs,
                streamer=streamer,
                max_new_tokens=config.MAX_NEW_TOKENS,
                do_sample=True,
                stopping_criteria=StoppingCriteriaList([_StopOnEvent()]),
                pad_token_id=self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id,
                **self.gen,
            )
            worker = threading.Thread(target=self.model.generate, kwargs=gen_kwargs, daemon=True)
            worker.start()
            try:
                yield from clean_stream(streamer)
            finally:
                stop.set()
                worker.join()

    def complete(self, messages: list[dict]) -> str:
        return "".join(self.stream(messages, threading.Event())).strip()


# ─────────────────────────── تنظيف مخرجات الموديل ───────────────────────────
_CLOSED_BLOCKS = re.compile(r"<think>.*?</think>|<\|channel>.*?<channel\|>", re.S)
_OPEN_BLOCK = re.compile(r"<think>|<\|channel>")
_SPECIAL = re.compile(
    r"<\|[^<>\s]{1,40}\|>|<\|[^<>\s]{1,40}>|<[^<>\s|]{1,40}\|>"      # <|im_end|>  <|turn>  <turn|>
    r"|</?(?:eos|bos|pad|s|end_of_turn|start_of_turn)>"               # <eos> </s> <end_of_turn>
)


def clean_text(raw: str, final: bool = False) -> str:
    """يشيل "تفكير" الموديل والرموز الخاصة، ويرجّع النص اللي ينفع يطلع للطفل."""
    out = _CLOSED_BLOCKS.sub("", raw)
    m = _OPEN_BLOCK.search(out)
    if m:                                   # تفكير ما خلص → نخفي كل اللي بعده
        out = out[: m.start()]
    out = _SPECIAL.sub("", out)
    if not final:                           # علامة "<" ناقصة بآخر النص → ننتظر لين تكمل
        cut = out.rfind("<")
        if cut != -1 and ">" not in out[cut:]:
            out = out[:cut]
    return out.lstrip()


def clean_stream(pieces: Iterable[str]) -> Iterator[str]:
    raw, sent = "", 0
    for piece in pieces:
        if not piece:
            continue
        raw += piece
        safe = clean_text(raw)
        if len(safe) > sent:
            yield safe[sent:]
            sent = len(safe)
    final = clean_text(raw, final=True).rstrip()
    if len(final) > sent:
        yield final[sent:]


# ─────────────────────────── تحميل مرن يناسب أنواع الموديلات ───────────────────────────
def _load_tokenizer(tf, model_id: str):
    try:
        return tf.AutoTokenizer.from_pretrained(model_id)
    except Exception:
        proc = tf.AutoProcessor.from_pretrained(model_id)
        return getattr(proc, "tokenizer", proc)


def _load_model(tf, model_id: str, kwargs: dict):
    errors = []
    for cls_name in ("AutoModelForCausalLM", "AutoModelForMultimodalLM", "AutoModelForImageTextToText"):
        cls = getattr(tf, cls_name, None)
        if cls is None:
            continue
        try:
            return cls.from_pretrained(model_id, **kwargs)
        except ValueError as exc:            # نوع الموديل ما يناسب هذا الكلاس → نجرب اللي بعده
            errors.append(f"{cls_name}: {exc}")
    raise RuntimeError("Could not load model:\n" + "\n".join(errors))


def get_engine():
    return MockEngine() if config.MOCK else TransformersEngine(config.MODEL_ID, config.LOAD_4BIT)
