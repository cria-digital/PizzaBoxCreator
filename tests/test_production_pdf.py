from __future__ import annotations

import json

import pytest
from PIL import Image

from app.print_specs.pdf_boxes import inspect_pdf
from app.print_specs.production_pdf import (
    build_artwork_pdf,
    build_cmyk_artwork_pdf,
    image_xobject_color_spaces,
    write_pdf_metadata,
)


def _write_spec(path):
    spec = {
        "dpi": 300,
        "canvas_px": {"width": 600, "height": 300},
        "bleed_size_mm": {"width": 50.8, "height": 25.4},
        "trim_size_mm": {"width": 44.45, "height": 19.05},
        "bleed_mm": {"left": 3.175, "right": 3.175, "bottom": 3.175, "top": 3.175},
    }
    path.write_text(json.dumps(spec), encoding="utf-8")


def test_build_artwork_pdf_sets_page_boxes_from_spec(tmp_path):
    master = tmp_path / "master.png"
    spec = tmp_path / "spec.json"
    output = tmp_path / "arte.pdf"
    Image.new("RGB", (600, 300), "orange").save(master)
    _write_spec(spec)

    result = build_artwork_pdf(master_path=master, spec_path=spec, output_path=output)

    inspected = inspect_pdf(output, dpi=300)
    assert result["color_mode"] == "RGB"
    assert inspected["boxes"]["MediaBox"]["mm"]["width"] == pytest.approx(50.8)
    assert inspected["boxes"]["BleedBox"]["mm"]["width"] == pytest.approx(50.8)
    assert inspected["boxes"]["TrimBox"]["mm"]["width"] == pytest.approx(44.45)
    assert inspected["bleed"]["mm"] == {"left": 3.17, "right": 3.17, "bottom": 3.17, "top": 3.17}


def test_build_artwork_pdf_rejects_wrong_master_size(tmp_path):
    master = tmp_path / "wrong.png"
    spec = tmp_path / "spec.json"
    output = tmp_path / "arte.pdf"
    Image.new("RGB", (300, 300), "orange").save(master)
    _write_spec(spec)

    with pytest.raises(ValueError, match="spec exige"):
        build_artwork_pdf(master_path=master, spec_path=spec, output_path=output)


def test_build_cmyk_artwork_pdf_preserves_device_cmyk_image(tmp_path):
    cmyk = tmp_path / "master_cmyk.tif"
    spec = tmp_path / "spec.json"
    output = tmp_path / "arte_cmyk.pdf"
    Image.new("CMYK", (600, 300), (0, 128, 255, 20)).save(cmyk)
    _write_spec(spec)

    result = build_cmyk_artwork_pdf(cmyk_path=cmyk, spec_path=spec, output_path=output)

    inspected = inspect_pdf(output, dpi=300)
    assert result["color_mode"] == "CMYK"
    assert "/DeviceCMYK" in result["image_color_spaces"]
    assert image_xobject_color_spaces(output) == ["/DeviceCMYK"]
    assert inspected["boxes"]["BleedBox"]["mm"]["width"] == pytest.approx(50.8)
    assert inspected["boxes"]["TrimBox"]["mm"]["width"] == pytest.approx(44.45)


def test_build_cmyk_artwork_pdf_rejects_rgb_input(tmp_path):
    rgb = tmp_path / "master_rgb.png"
    spec = tmp_path / "spec.json"
    output = tmp_path / "arte_cmyk.pdf"
    Image.new("RGB", (600, 300), "orange").save(rgb)
    _write_spec(spec)

    with pytest.raises(ValueError, match="CMYK"):
        build_cmyk_artwork_pdf(cmyk_path=rgb, spec_path=spec, output_path=output)


def test_write_pdf_metadata(tmp_path):
    output = tmp_path / "arte.pdf"
    metadata = write_pdf_metadata({"pdf": str(output)}, output)

    assert metadata == tmp_path / "arte.json"
    assert json.loads(metadata.read_text())["pdf"] == str(output)
