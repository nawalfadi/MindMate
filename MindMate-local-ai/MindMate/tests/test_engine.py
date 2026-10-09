"""اختبارات المحرك والشخصية — بدون GPU:  python -m pytest -q"""
import pytest

import engine


@pytest.mark.parametrize("pieces,expected", [
    # Qwen: تفكير مخفي + رمز نهاية
    (["<think>", "أفكر…", "</think>", "\n\nهلا! ", "كيفك؟", "<|im_end|>"], "هلا! كيفك؟"),
    # Gemma 4: قناة تفكير + علامة نهاية الدور
    (["<|channel>", "thought\n", "<channel|>", "أهلين", " يا بطل", "<turn|>"], "أهلين يا بطل"),
    # رموز خاصة مقطوعة بين قطعتين
    (["تمام ", "<tu", "rn|>"], "تمام"),
    # نص عادي فيه "<" حقيقية
    (["3 ", "< 5 صح"], "3 < 5 صح"),
    # تفكير ما خلص أبداً → ما يطلع منه شي
    (["هلا ", "<think>", "سر"], "هلا"),
])
def test_clean_stream(pieces, expected):
    assert "".join(engine.clean_stream(pieces)).strip() == expected


def test_presets_by_model():
    assert engine.preset_for("google/gemma-4-12B-it")["top_k"] == 64
    assert engine.preset_for("Qwen/Qwen3-14B")["top_k"] == 20
