"""Logo preparation: PNG output, background-removal hook, and graceful fallbacks."""

from __future__ import annotations

import io

from PIL import Image

from app.config import settings
from app.services import logo_service
from app.services.logo_service import prepare_logo


def _png_bytes(color=(120, 200, 80, 255), size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_prepare_logo_writes_png_even_for_jpg_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "logo_remove_background", False)
    dest = tmp_path / "logo.jpg"

    out = prepare_logo(_png_bytes(), dest)

    assert out.suffix == ".png" and out.exists()
    assert Image.open(out).mode == "RGBA"


def test_prepare_logo_keeps_raw_bytes_when_not_an_image(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "logo_remove_background", False)
    dest = tmp_path / "logo.png"

    out = prepare_logo(b"not-a-real-image", dest)

    assert out.exists()
    assert out.read_bytes() == b"not-a-real-image"


def test_prepare_logo_uses_background_removal_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "logo_remove_background", True)

    # Stand in for rembg: return a distinctive transparent image so we can detect it was used.
    sentinel = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    called = {}

    def fake_remove(image_bytes):
        called["yes"] = True
        return sentinel

    monkeypatch.setattr(logo_service, "_remove_background", fake_remove)
    out = prepare_logo(_png_bytes(), tmp_path / "logo.png")

    assert called.get("yes")
    assert Image.open(out).size == (10, 10)


def test_prepare_logo_falls_back_when_removal_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "logo_remove_background", False)

    def boom(_):
        raise AssertionError("background removal should not run when disabled")

    monkeypatch.setattr(logo_service, "_remove_background", boom)
    out = prepare_logo(_png_bytes(size=(32, 48)), tmp_path / "logo.png")

    assert Image.open(out).size == (32, 48)


def test_remove_background_returns_original_when_rembg_missing(tmp_path, monkeypatch):
    """With rembg not installed, removal degrades to the original image (not None-crash)."""
    monkeypatch.setattr(settings, "logo_remove_background", True)
    # rembg genuinely isn't a dependency in the test env, so the import fails internally
    # and _remove_background returns None -> prepare_logo keeps the decoded original.
    out = prepare_logo(_png_bytes(size=(20, 20)), tmp_path / "logo.png")
    assert Image.open(out).size == (20, 20)
