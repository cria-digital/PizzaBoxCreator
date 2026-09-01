from __future__ import annotations

import json

import pytest
from pypdf import PdfWriter

from scripts.inspect_pdf_boxes import format_human, inspect_pdf


def _write_pdf_with_boxes(path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=900, height=500)
    page.trimbox.lower_left = (20, 30)
    page.trimbox.upper_right = (820, 430)
    page.bleedbox.lower_left = (10, 20)
    page.bleedbox.upper_right = (830, 440)
    with path.open("wb") as stream:
        writer.write(stream)


def test_inspect_pdf_reports_explicit_trim_bleed_and_canvas(tmp_path):
    pdf = tmp_path / "boxes.pdf"
    _write_pdf_with_boxes(pdf)

    result = inspect_pdf(pdf, page_number=1, dpi=300)

    assert result["page_count"] == 1
    assert result["boxes"]["MediaBox"]["explicit"] is True
    assert result["boxes"]["TrimBox"]["explicit"] is True
    assert result["boxes"]["BleedBox"]["explicit"] is True
    assert result["boxes"]["TrimBox"]["points"]["width"] == 800
    assert result["boxes"]["TrimBox"]["points"]["height"] == 400
    assert result["boxes"]["TrimBox"]["mm"]["width"] == pytest.approx(282.22)
    assert result["boxes"]["TrimBox"]["pixels"] == {"width": 3333, "height": 1667}
    assert result["bleed"]["points"] == {"left": 10, "right": 10, "bottom": 10, "top": 10}
    assert result["bleed"]["mm"]["left"] == pytest.approx(3.53)
    assert result["recommended_canvas_box"] == "BleedBox"


def test_inspect_pdf_json_serializable_and_human_readable(tmp_path):
    pdf = tmp_path / "boxes.pdf"
    _write_pdf_with_boxes(pdf)

    result = inspect_pdf(pdf, page_number=1, dpi=350)

    json.dumps(result)
    human = format_human(result)
    assert "TrimBox" in human
    assert "Canvas recomendado: BleedBox" in human


def test_inspect_pdf_rejects_invalid_page(tmp_path):
    pdf = tmp_path / "boxes.pdf"
    _write_pdf_with_boxes(pdf)

    with pytest.raises(ValueError, match="fora do intervalo"):
        inspect_pdf(pdf, page_number=2, dpi=300)
