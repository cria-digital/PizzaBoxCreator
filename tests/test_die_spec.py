from __future__ import annotations

import json

import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject

from app.print_specs.die_spec import build_die_spec, write_die_spec


def _write_pdf(path, *, trim=True, bleed=True):
    writer = PdfWriter()
    page = writer.add_blank_page(width=900, height=500)
    page.pop(NameObject("/BleedBox"), None)
    page.pop(NameObject("/TrimBox"), None)
    if trim:
        page.trimbox.lower_left = (20, 30)
        page.trimbox.upper_right = (820, 430)
    if bleed:
        page.bleedbox.lower_left = (10, 20)
        page.bleedbox.upper_right = (830, 440)
    with path.open("wb") as stream:
        writer.write(stream)


def test_build_die_spec_uses_bleedbox_as_canvas(tmp_path):
    pdf = tmp_path / "faca.pdf"
    _write_pdf(pdf)

    spec = build_die_spec(pdf, name="teste_35", product_type="pizza_box", dpi=300)

    assert spec["schema_version"] == 1
    assert spec["name"] == "teste_35"
    assert spec["cutline_source"] == "TrimBox"
    assert spec["canvas_source"] == "BleedBox"
    assert spec["trim_size_mm"]["width"] == pytest.approx(282.22)
    assert spec["bleed_size_mm"]["width"] == pytest.approx(289.28)
    assert spec["bleed_mm"] == {"left": 3.53, "right": 3.53, "bottom": 3.53, "top": 3.53}
    assert spec["canvas_px"] == {"width": 3417, "height": 1750}
    assert "linha de corte" in spec["prompt_constraints"]["must_not_draw"]


def test_write_die_spec_round_trips_json(tmp_path):
    pdf = tmp_path / "faca.pdf"
    out = tmp_path / "specs" / "faca.json"
    _write_pdf(pdf)
    spec = build_die_spec(pdf, name="teste_35")

    write_die_spec(spec, out)

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["name"] == "teste_35"
    assert loaded["canvas_source"] == "BleedBox"


def test_build_die_spec_requires_explicit_bleedbox(tmp_path):
    pdf = tmp_path / "sem_bleed.pdf"
    _write_pdf(pdf, bleed=False)

    with pytest.raises(ValueError, match="BleedBox"):
        build_die_spec(pdf, name="sem_bleed")
