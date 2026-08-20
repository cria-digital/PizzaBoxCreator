"""Calibration: reading layer geometry, persisting it, and applying it in the engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.commands import EditCommand
from app.psd.calibration import (
    read_template_geometry, merge_geometry, split_layer_name, layers_for_base, field_label,
)
from app.psd.engine import PsdEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"

pytestmark = pytest.mark.skipif(
    not REAL_TEMPLATE.exists(), reason="rode `python scripts/create_test_template.py` primeiro"
)


def test_read_template_geometry_returns_canvas_and_editable_boxes():
    geo = read_template_geometry(REAL_TEMPLATE)

    assert geo.width > 0 and geo.height > 0
    names = {b.name for b in geo.boxes}
    assert {"TEXTO_TELEFONE", "TEXTO_INSTAGRAM", "TEXTO_FRASE_OPCIONAL", "LOGO_CLIENTE"} <= names

    text_box = next(b for b in geo.boxes if b.name == "TEXTO_TELEFONE")
    assert text_box.kind == "text" and text_box.font_size and text_box.width > 0

    logo_box = next(b for b in geo.boxes if b.name == "LOGO_CLIENTE")
    assert logo_box.kind == "logo" and logo_box.font_size is None


def test_merge_geometry_overlays_saved_values_on_defaults():
    geo = read_template_geometry(REAL_TEMPLATE)
    calibration = {"TEXTO_TELEFONE": {"x": 700, "y": 1500, "font_size": 80}}

    merged = merge_geometry(geo, calibration)
    tel = next(b for b in merged if b["name"] == "TEXTO_TELEFONE")

    assert tel["x"] == 700 and tel["y"] == 1500 and tel["font_size"] == 80
    # width/height fall back to the PSD default since calibration didn't override them
    assert tel["width"] > 0


def test_apply_text_calibration_repositions_and_resizes_layer():
    calibration = {"TEXTO_TELEFONE": {"x": 800, "y": 1600, "width": 600,
                                      "height": 90, "font_size": 72}}
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(telefone="(11) 90000-0000"), calibration=calibration)

    layer = engine.find_layer("TEXTO_TELEFONE")
    assert layer.transform_tx == 800
    # baseline = box top (y) + font size, so the renderer draws the text at y
    assert layer.transform_ty == 1600 + 72
    assert round(layer.style_run_font_size(0)) == 72


def test_apply_logo_calibration_resizes_and_moves_layer(tmp_path, monkeypatch):
    from PIL import Image

    import app.psd.engine as engine_module

    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (300, 300), (10, 20, 30, 255)).save(logo_path)
    monkeypatch.setattr(engine_module, "ALLOWED_LOGO_ROOTS", (tmp_path,))

    calibration = {"LOGO_CLIENTE": {"x": 1500, "y": 900, "width": 500, "height": 400}}
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(logo_path=str(logo_path)), calibration=calibration)

    layer = engine.find_layer("LOGO_CLIENTE")
    assert layer.width == 500 and layer.height == 400
    assert layer.center_x == 1500 and layer.center_y == 900


def test_apply_without_calibration_leaves_default_positions():
    engine = PsdEngine(REAL_TEMPLATE)
    before_tx = engine.find_layer("TEXTO_TELEFONE").transform_tx

    engine.apply(EditCommand(telefone="(11) 90000-0000"))
    assert engine.find_layer("TEXTO_TELEFONE").transform_tx == before_tx


def test_calibration_round_trips_through_repository(db, sample_template):
    from app.db import repositories as repo

    calibration = {"TEXTO_TELEFONE": {"x": 700.0, "y": 1500.0, "font_size": 80.0}}
    repo.template_set_calibration(db, sample_template["id"], calibration)

    fetched = repo.template_get(db, sample_template["id"])
    assert fetched["calibration"] == calibration


# ---------------------------------------------------------------------------
# Dual-face (DUPLA box): one layer per field per face
# ---------------------------------------------------------------------------

def test_split_layer_name_parses_face_suffix():
    assert split_layer_name("TEXTO_TELEFONE") == ("TEXTO_TELEFONE", 1)
    assert split_layer_name("TEXTO_TELEFONE_2") == ("TEXTO_TELEFONE", 2)
    assert split_layer_name("TEXTO_FRASE_OPCIONAL_3") == ("TEXTO_FRASE_OPCIONAL", 3)
    assert split_layer_name("LOGO_CLIENTE") == ("LOGO_CLIENTE", 1)


def test_split_layer_name_accepts_unnamed_layers():
    assert split_layer_name("") == ("", 1)
    assert split_layer_name(None) == ("", 1)


def test_layers_for_base_groups_and_orders_faces():
    names = ["TEXTO_TELEFONE_2", "TEXTO_TELEFONE", "TEXTO_INSTAGRAM", "LOGO_CLIENTE"]
    assert layers_for_base(names, "TEXTO_TELEFONE") == ["TEXTO_TELEFONE", "TEXTO_TELEFONE_2"]
    assert layers_for_base(names, "TEXTO_INSTAGRAM") == ["TEXTO_INSTAGRAM"]


def test_field_label_marks_mirror_faces():
    assert field_label("TEXTO_TELEFONE") == "Telefone"
    assert field_label("TEXTO_TELEFONE_2") == "Telefone (2)"


def test_geometry_discovers_both_faces():
    geo = read_template_geometry(REAL_TEMPLATE)
    names = {b.name for b in geo.boxes}
    assert "TEXTO_TELEFONE" in names and "TEXTO_TELEFONE_2" in names
    assert "LOGO_CLIENTE" in names and "LOGO_CLIENTE_2" in names


def test_set_text_fills_every_face():
    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(telefone="(11) 91234-5678"))

    assert engine.find_layer("TEXTO_TELEFONE").text == "(11) 91234-5678"
    assert engine.find_layer("TEXTO_TELEFONE_2").text == "(11) 91234-5678"
    assert sum("TEXTO_TELEFONE" in c for c in changes) >= 2


def test_replace_logo_fills_every_face(tmp_path, monkeypatch):
    from PIL import Image

    import app.psd.engine as engine_module

    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (300, 300), (10, 20, 30, 255)).save(logo_path)
    monkeypatch.setattr(engine_module, "ALLOWED_LOGO_ROOTS", (tmp_path,))

    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(logo_path=str(logo_path)))

    assert engine.find_layer("LOGO_CLIENTE").has_mask()
    assert engine.find_layer("LOGO_CLIENTE_2").has_mask()


def test_toggle_decoration_activates_every_face():
    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(adicionar_selo_entrega=True))

    assert engine.find_layer("selo_entrega_rapida").is_visible is True
    assert engine.find_layer("selo_entrega_rapida_2").is_visible is True
    assert any("selo_entrega_rapida" in c for c in changes)


def test_per_face_calibration_positions_each_face_independently():
    calibration = {
        "TEXTO_TELEFONE":   {"x": 200, "y": 800, "font_size": 40},
        "TEXTO_TELEFONE_2": {"x": 1200, "y": 800, "font_size": 40},
    }
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(telefone="(11) 90000-0000"), calibration=calibration)

    assert engine.find_layer("TEXTO_TELEFONE").transform_tx == 200
    assert engine.find_layer("TEXTO_TELEFONE_2").transform_tx == 1200
