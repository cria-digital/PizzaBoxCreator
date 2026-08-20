"""Bridging a flattened PSD into an editable gabarito."""

from __future__ import annotations

import numpy as np
import photoshopapi as psapi
import pytest

from app.psd.fields import build_editable_fields
from app.psd.gabarito_builder import (
    build_editable_gabarito, is_editable_gabarito, detect_reserved_box, detect_reserved_boxes,
)


def _make_flat_psd(path, w=600, h=600):
    """A flattened RGB art with a solid white reserved box at the bottom-center."""
    cid = psapi.enum.ChannelID
    img = np.full((h, w, 3), 200, np.uint8)   # tan background
    img[int(h * 0.82):int(h * 0.92), int(w * 0.33):int(w * 0.66)] = 255  # reserved box
    f = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, w, h)
    f.add_layer(psapi.ImageLayer_8bit(
        {cid.red: np.ascontiguousarray(img[:, :, 0]),
         cid.green: np.ascontiguousarray(img[:, :, 1]),
         cid.blue: np.ascontiguousarray(img[:, :, 2])},
        "Camada 1", width=w, height=h, pos_x=w // 2, pos_y=h // 2))
    f.write(str(path))


def test_detect_reserved_box_finds_solid_white_rectangle():
    arr = np.full((600, 600, 3), 200, np.uint8)
    arr[490:560, 200:400] = 255
    box = detect_reserved_box(arr)
    assert box is not None
    x, y, bw, bh = box
    assert 180 <= x <= 220 and 380 <= x + bw <= 420
    assert 60 <= bh <= 80


def test_detect_reserved_boxes_separates_box_faces():
    arr = np.full((600, 1200, 3), 200, np.uint8)
    arr[490:560, 170:350] = 255
    arr[490:560, 770:950] = 255

    boxes = detect_reserved_boxes(arr)

    assert len(boxes) == 2
    assert boxes[0][0] < 300
    assert boxes[1][0] > 700


def test_flat_psd_is_not_editable_but_bridged_one_is(tmp_path):
    flat = tmp_path / "flat.psd"
    _make_flat_psd(flat)
    assert is_editable_gabarito(flat) is False

    out = tmp_path / "editavel.psd"
    calibration = build_editable_gabarito(flat, out)

    assert is_editable_gabarito(out) is True
    names = {l.name for l in psapi.LayeredFile.read(str(out)).flat_layers}
    assert {"fundo_kraft_tradicional", "LOGO_CLIENTE",
            "TEXTO_TELEFONE", "TEXTO_INSTAGRAM"} <= names

    # Calibration positions the fields inside the detected reserved box.
    assert {"LOGO_CLIENTE", "TEXTO_TELEFONE", "TEXTO_INSTAGRAM"} <= set(calibration)
    for entry in calibration.values():
        assert entry["x"] >= 0 and entry["y"] >= 0

    fields = build_editable_fields(out)
    assert "tema_fundo" not in {field["name"] for field in fields}


def test_ready_template_is_detected_as_editable():
    from pathlib import Path
    real = Path(__file__).resolve().parents[1] / "gabaritos" / "caixa_35cm_teste.psd"
    if not real.exists():
        pytest.skip("rode create_test_template.py primeiro")
    assert is_editable_gabarito(real) is True
