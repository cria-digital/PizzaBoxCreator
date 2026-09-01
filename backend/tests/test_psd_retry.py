"""Transient-failure retry around native PhotoshopAPI read/write, and channel ordering."""

from __future__ import annotations

import numpy as np
import pytest

from app.psd import engine


def test_rgb_channels_selects_by_id_not_position():
    """get_image_data() can return channels as [0, 2, 1]; we must index by id, not order."""
    red = np.full((2, 2), 200, np.uint8)
    green = np.full((2, 2), 100, np.uint8)
    blue = np.full((2, 2), 50, np.uint8)
    # Insertion order R, B, G (the order a real PSD exposed) -- positional read would swap G/B.
    data = {0: red, 2: blue, 1: green}

    r, g, b = engine.rgb_channels(data)
    assert int(r[0, 0]) == 200 and int(g[0, 0]) == 100 and int(b[0, 0]) == 50


def test_rgb_channels_returns_none_for_non_rgb():
    assert engine.rgb_channels({0: np.zeros((2, 2), np.uint8)}) is None


def test_text_fill_rgb_reads_renderer_channel_order():
    class FakeLayer:
        def style_run_fill_color(self, _run):
            return [1.0, 0.2, 0.4, 0.8]  # [a, g, b, r]
    assert engine.text_fill_rgb(FakeLayer()) == (204, 51, 102)


def test_text_fill_rgb_falls_back_to_black_on_error():
    class Broken:
        def style_run_fill_color(self, _run):
            raise RuntimeError("no color")
    assert engine.text_fill_rgb(Broken()) == (0, 0, 0)


def test_rgb_to_cmyk_color_naive_extremes():
    assert engine._rgb_to_cmyk_color(255, 255, 255, None) == [0.0, 0.0, 0.0, 0.0]  # white
    assert engine._rgb_to_cmyk_color(0, 0, 0, None) == [0.0, 0.0, 0.0, 1.0]        # black
    assert engine._rgb_to_cmyk_color(255, 0, 0, None) == [0.0, 1.0, 1.0, 0.0]      # red


def test_retry_native_succeeds_after_transient_failures(monkeypatch):
    monkeypatch.setattr(engine.time, "sleep", lambda *_: None)  # no real backoff in tests
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("native hiccup")
        return "ok"

    assert engine._retry_native(flaky, what="teste", attempts=3) == "ok"
    assert calls["n"] == 3


def test_retry_native_reraises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(engine.time, "sleep", lambda *_: None)

    def always_fails():
        raise RuntimeError("persistente")

    with pytest.raises(RuntimeError, match="persistente"):
        engine._retry_native(always_fails, what="teste", attempts=3)


def test_psd_read_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(engine.time, "sleep", lambda *_: None)
    attempts = {"n": 0}

    def fake_read(path):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("file busy")
        return f"file:{path}"

    monkeypatch.setattr(engine.psapi.LayeredFile, "read", staticmethod(fake_read))
    assert engine.psd_read("foo.psd") == "file:foo.psd"
    assert attempts["n"] == 2
