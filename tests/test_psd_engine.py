import numpy as np
from PIL import Image

from app.psd.engine import _check_text_overflow, _fit_logo_to_layer


class FakeTextLayer:
    """Stands in for a psapi.TextLayer_8bit without needing a real PSD on disk."""

    def __init__(self, box_width, box_height, font_size, name="TEXTO_TESTE"):
        self.is_box_text = True
        self.name = name
        self._box_width = box_width
        self._box_height = box_height
        self._font_size = font_size

    def box_width(self):
        return self._box_width

    def box_height(self):
        return self._box_height

    def style_run_font_size(self, _index):
        return self._font_size


def test_fit_logo_preserves_aspect_ratio():
    # wide logo (400x100, ratio 4:1) fit into a square 200x200 layer
    logo = Image.new("RGBA", (400, 100), (10, 200, 60, 255))
    rgb, mask = _fit_logo_to_layer(logo, 200, 200)

    assert rgb.size == (200, 200)
    assert mask.shape == (200, 200)

    # scaled logo should be 200x50 (same 4:1 ratio), centered vertically
    opaque_rows = np.where(mask.max(axis=1) > 0)[0]
    assert opaque_rows.max() - opaque_rows.min() + 1 == 50


def test_fit_logo_preserves_transparency_hole():
    arr = np.zeros((100, 100, 4), dtype=np.uint8)
    arr[:, :, :3] = 50
    arr[:, :, 3] = 255
    arr[40:60, 40:60, 3] = 0  # punch a transparent hole in the middle
    logo = Image.fromarray(arr, "RGBA")

    rgb, mask = _fit_logo_to_layer(logo, 100, 100)
    assert mask[50, 50] == 0
    assert mask[10, 10] == 255


def test_fit_logo_does_not_stretch_when_already_matching_ratio():
    logo = Image.new("RGBA", (200, 200), (1, 2, 3, 255))
    rgb, mask = _fit_logo_to_layer(logo, 200, 200)
    assert mask.min() == 255  # fully opaque, no padding added


def test_check_text_overflow_flags_long_text_in_small_box():
    layer = FakeTextLayer(box_width=150, box_height=30, font_size=24)
    warning = _check_text_overflow(
        layer, "Um texto bem mais longo do que cabe nessa caixa pequena"
    )
    assert warning is not None
    assert "AVISO" in warning


def test_check_text_overflow_ok_for_short_text():
    layer = FakeTextLayer(box_width=400, box_height=100, font_size=24)
    assert _check_text_overflow(layer, "Oi") is None


def test_check_text_overflow_skips_point_text():
    layer = FakeTextLayer(box_width=10, box_height=10, font_size=24)
    layer.is_box_text = False
    assert _check_text_overflow(layer, "Texto bem longo que normalmente vazaria a caixa") is None
