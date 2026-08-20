"""PsdEngine.apply() against the real synthetic template (gabaritos/caixa_35cm_teste.psd),
isolated from the order/preview pipeline tested elsewhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.commands import EditCommand, TemaFundo
from app.psd.engine import PsdEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"

pytestmark = pytest.mark.skipif(
    not REAL_TEMPLATE.exists(), reason="rode `python scripts/create_test_template.py` primeiro"
)


def test_set_text_changes_layer_and_reports_change():
    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(telefone="(11) 90000-0000"))

    assert any("TEXTO_TELEFONE" in c for c in changes)
    assert engine.find_layer("TEXTO_TELEFONE").text == "(11) 90000-0000"


def test_set_text_on_unknown_layer_returns_warning():
    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine._set_text("CAMADA_QUE_NAO_EXISTE", "qualquer coisa")
    assert any("AVISO" in c and "nao encontrada" in c for c in changes)


def test_set_background_premium_toggles_visibility():
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(tema_fundo=TemaFundo.premium))

    assert engine.find_layer("fundo_preto_premium").is_visible is True
    assert engine.find_layer("fundo_kraft_tradicional").is_visible is False


def test_set_background_tradicional_toggles_visibility():
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(tema_fundo=TemaFundo.tradicional))

    assert engine.find_layer("fundo_kraft_tradicional").is_visible is True
    assert engine.find_layer("fundo_preto_premium").is_visible is False


def test_toggle_layer_selo_entrega():
    engine = PsdEngine(REAL_TEMPLATE)
    assert engine.find_layer("selo_entrega_rapida").is_visible is False

    engine.apply(EditCommand(adicionar_selo_entrega=True))
    assert engine.find_layer("selo_entrega_rapida").is_visible is True


def test_toggle_layer_forno_lenha():
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(adicionar_forno_lenha=True))
    assert engine.find_layer("ilustracao_forno_lenha").is_visible is True


def test_replace_logo_with_real_image(tmp_path, monkeypatch):
    from PIL import Image

    import app.psd.engine as engine_module

    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (300, 100), (10, 20, 30, 255)).save(logo_path)

    # ALLOWED_LOGO_ROOTS is computed once at import time from settings, so point it at
    # tmp_path directly instead of relying on the (already-imported) real config dirs.
    monkeypatch.setattr(engine_module, "ALLOWED_LOGO_ROOTS", (tmp_path,))

    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(logo_path=str(logo_path)))

    assert any("Logo substituido" in c for c in changes)
    assert engine.find_layer("LOGO_CLIENTE").has_mask()


def test_replace_logo_rejects_path_outside_allowed_roots(tmp_path, monkeypatch):
    import app.psd.engine as engine_module

    monkeypatch.setattr(engine_module, "ALLOWED_LOGO_ROOTS", (tmp_path / "only_this_dir",))

    outside_path = tmp_path / "elsewhere" / "logo.png"
    outside_path.parent.mkdir()
    outside_path.write_bytes(b"fake")

    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(logo_path=str(outside_path)))
    assert any("nao permitido" in c for c in changes)


def test_replace_logo_with_invalid_file_returns_warning_not_crash(tmp_path, monkeypatch):
    import app.psd.engine as engine_module

    monkeypatch.setattr(engine_module, "ALLOWED_LOGO_ROOTS", (tmp_path,))

    bad_path = tmp_path / "corrupted.png"
    bad_path.write_bytes(b"isso nao e uma imagem")

    engine = PsdEngine(REAL_TEMPLATE)
    changes = engine.apply(EditCommand(logo_path=str(bad_path)))
    assert any("AVISO" in c and "invalido" in c for c in changes)


def test_save_and_save_as_cmyk_roundtrip(tmp_path):
    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(telefone="(11) 90000-0000"))

    out = tmp_path / "out.psd"
    engine.save(out)
    assert out.exists()

    cmyk_out = tmp_path / "out_cmyk.psd"
    engine.save_as_cmyk(cmyk_out, source_psd=out)
    assert cmyk_out.exists()

    import photoshopapi as psapi

    cmyk_file = psapi.LayeredFile.read(str(cmyk_out))
    assert cmyk_file.num_channels >= 4

    # The CMYK text layer must carry an explicit fill color (4 CMYK values), so production
    # text matches the approved preview instead of defaulting to an invisible color.
    text_layer = next(l for l in cmyk_file.flat_layers if l.name == "TEXTO_TELEFONE")
    fill = text_layer.style_run_fill_color(0)
    assert fill and len(fill) == 4

    # Paragraph-box wrapping is preserved so long text breaks like the preview did.
    src_box_width = engine.find_layer("TEXTO_TELEFONE").box_width()
    assert text_layer.is_box_text
    assert abs(text_layer.box_width() - src_box_width) < 1.0

    # The full-canvas background must land at the canvas top-left in the CMYK file, not shift
    # half a canvas off-screen (regression: pos was set from center_x without the +w/2 offset).
    bg = next(l for l in cmyk_file.flat_layers if l.name == "fundo_kraft_tradicional")
    top_left_x = bg.center_x - bg.width / 2
    top_left_y = bg.center_y - bg.height / 2
    assert abs(top_left_x) <= 2 and abs(top_left_y) <= 2


def test_cmyk_export_stamps_production_dpi(tmp_path, monkeypatch):
    import photoshopapi as psapi

    from app.config import settings

    monkeypatch.setattr(settings, "production_dpi", 350)

    engine = PsdEngine(REAL_TEMPLATE)
    engine.apply(EditCommand(telefone="(11) 90000-0000"))
    out = tmp_path / "out.psd"
    engine.save(out)

    cmyk_out = tmp_path / "out_cmyk.psd"
    dropped = engine.save_as_cmyk(cmyk_out, source_psd=out)

    assert dropped == []  # clean template drops nothing
    assert psapi.LayeredFile.read(str(cmyk_out)).dpi == 350.0


def test_unsupported_layers_empty_for_clean_template():
    engine = PsdEngine(REAL_TEMPLATE)
    assert engine.unsupported_layers() == []


def test_font_warnings_flags_missing_font(monkeypatch):
    import app.psd.engine as engine_module

    engine = PsdEngine(REAL_TEMPLATE)
    # Font installed -> no warning.
    assert engine.font_warnings() == []

    # Font missing -> one warning per distinct font, naming it.
    monkeypatch.setattr(engine_module, "font_available", lambda name: False)
    warnings = engine.font_warnings()
    assert warnings and all("AVISO" in w and "fonte" in w for w in warnings)
