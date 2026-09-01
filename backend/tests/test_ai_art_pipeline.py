from __future__ import annotations

import io
import json

from PIL import Image

from app.print_specs.ai_art_pipeline import (
    die_aspect_ratio,
    load_references,
    prepare_generation_references,
    provider_aspect_ratio_for_die,
    run_ai_art_pipeline,
    save_generated_image,
)
from app.print_specs.panel_treatment import blank_design_panel


def _png_bytes(size=(64, 36), color=(10, 20, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _write_spec(path):
    spec = {
        "schema_version": 1,
        "name": "teste",
        "dpi": 300,
        "canvas_px": {"width": 600, "height": 300},
        "bleed_size_mm": {"width": 50.8, "height": 25.4},
        "trim_size_mm": {"width": 44.45, "height": 19.05},
        "bleed_mm": {"left": 3.175, "right": 3.175, "bottom": 3.175, "top": 3.175},
        "aspect_ratio": 2.0,
        "prompt_constraints": {
            "must_not_draw": ["faca", "linha de corte"],
        },
        "boxes": {
            "MediaBox": {"points": {"left": 0, "bottom": 0, "right": 144, "top": 72, "width": 144, "height": 72}},
            "BleedBox": {"points": {"left": 0, "bottom": 0, "right": 144, "top": 72, "width": 144, "height": 72}},
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")


def _fake_overlay(**kwargs):
    Image.new("RGB", (600, 300), (20, 30, 40)).save(kwargs["output_path"], "JPEG")
    return kwargs["output_path"]


def test_save_generated_image_normalizes_to_png(tmp_path):
    out = tmp_path / "generated.png"

    save_generated_image(_png_bytes(), out)

    assert Image.open(out).mode == "RGB"


def test_load_references_reads_media_types(tmp_path):
    png = tmp_path / "ref.png"
    jpg = tmp_path / "ref.jpg"
    png.write_bytes(_png_bytes())
    jpg.write_bytes(_png_bytes())

    refs = load_references([png, jpg])

    assert refs[0][1] == "image/png"
    assert refs[1][1] == "image/jpeg"


def test_load_references_preserves_transparent_logo_alpha(tmp_path):
    logo = tmp_path / "logo.png"
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    image.putpixel((4, 4), (255, 0, 0, 255))
    image.save(logo)

    data, media_type = load_references([logo])[0]
    preserved = Image.open(io.BytesIO(data)).convert("RGBA")

    assert media_type == "image/png"
    assert preserved.getpixel((0, 0))[3] == 0
    assert preserved.getpixel((4, 4)) == (255, 0, 0, 255)


def test_load_references_crops_white_logo_margins(tmp_path):
    logo = tmp_path / "logo.png"
    image = Image.new("RGB", (400, 300), "white")
    for x in range(150, 250):
        for y in range(110, 190):
            image.putpixel((x, y), (165, 48, 32))
    image.save(logo)

    data, media_type = load_references([logo])[0]
    cropped = Image.open(io.BytesIO(data)).convert("RGB")

    assert media_type == "image/png"
    assert cropped.width < 160
    assert cropped.height < 140
    assert cropped.getbbox() is not None


def test_die_aspect_ratio_uses_exact_canvas():
    assert die_aspect_ratio({"canvas_px": {"width": 9713, "height": 5154}}) == "5154:9713"


def test_provider_aspect_ratio_for_die_uses_supported_nearest():
    assert provider_aspect_ratio_for_die({"canvas_px": {"width": 9713, "height": 5154}}) == "9:16"


def test_prepare_generation_references_defaults_to_client_refs_only(tmp_path):
    client_ref = tmp_path / "cliente.jpg"
    client_ref.write_bytes(b"jpg")

    refs, guide, error = prepare_generation_references(
        job_id="job",
        die_pdf_path=tmp_path / "die.pdf",
        spec_path=tmp_path / "spec.json",
        client_reference_paths=[client_ref],
        temp_root=tmp_path,
    )

    assert error is None
    assert guide is None
    assert refs == [client_ref]


def test_prepare_generation_references_can_prepend_die_guide(tmp_path, monkeypatch):
    import app.print_specs.ai_art_pipeline as pipeline

    client_ref = tmp_path / "cliente.jpg"
    client_ref.write_bytes(b"jpg")

    def fake_guide(**kwargs):
        kwargs["output_path"].write_bytes(b"guide")
        return kwargs["output_path"]

    monkeypatch.setattr(pipeline, "build_die_generation_guide", fake_guide)

    refs, guide, error = prepare_generation_references(
        job_id="job",
        die_pdf_path=tmp_path / "die.pdf",
        spec_path=tmp_path / "spec.json",
        client_reference_paths=[client_ref],
        include_die_guide=True,
        temp_root=tmp_path,
    )

    assert error is None
    assert guide == tmp_path / "ai_pilot_guides" / "job_die_guide.png"
    assert refs == [guide, client_ref]


def test_blank_design_panel_clears_bottom_panel_from_template(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    Image.new("RGB", (300, 600), (12, 34, 56)).save(source)

    result = blank_design_panel(image_path=source, output_path=output)
    treated = Image.open(output).convert("RGB")

    assert result["applied"] is True
    assert result["panel"] == "bottom_panel"
    assert treated.getpixel((150, 120)) == (255, 255, 255)
    assert treated.getpixel((150, 500)) == (12, 34, 56)


def test_run_ai_art_pipeline_writes_all_outputs(tmp_path, monkeypatch):
    import app.print_specs.ai_art_pipeline as pipeline

    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    out = tmp_path / "art"
    pdfs = tmp_path / "pdf"
    _write_spec(spec)
    die.write_bytes(b"%PDF fake")
    calls = {}

    def fake_image_generation(*args, **kwargs):
        calls.update(kwargs)
        return _png_bytes()

    monkeypatch.setattr(pipeline, "image_generation", fake_image_generation)
    monkeypatch.setattr(pipeline, "prepare_generation_references", lambda **kwargs: (kwargs["client_reference_paths"], None, None))
    monkeypatch.setattr(pipeline, "build_preflight_overlay", _fake_overlay)
    monkeypatch.setattr(pipeline, "build_safety_overlay", _fake_overlay)
    def fake_compose(**kwargs):
        calls["compose_edit_data"] = kwargs["edit_data"]
        kwargs["output_path"].write_bytes(kwargs["art_path"].read_bytes())
        return {"safe_composed": True}

    monkeypatch.setattr(pipeline, "compose_safe_critical_content", fake_compose)

    result = run_ai_art_pipeline(
        job_id="job_teste",
        spec_path=spec,
        die_pdf_path=die,
        client={"name": "Yeti", "phone": "1999"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "tema_fundo": "premium"},
        output_root=out,
        pdf_output_dir=pdfs,
    )

    assert (out / "job_teste_ai_generated.png").exists()
    assert (out / "job_teste_ai_preview.jpg").exists()
    assert (out / "job_teste_master_raw.png").exists()
    assert (out / "job_teste_master.png").exists()
    assert (out / "job_teste_master_cmyk.tif").exists()
    assert (pdfs / "job_teste_arte_cmyk.pdf").exists()
    assert result["safety"].endswith("_safety.jpg")
    assert (out / "job_teste_pipeline.json").exists()
    assert result["pdf"]["image_color_spaces"] == ["/DeviceCMYK"]
    assert result["master"]["safe_composition"]["safe_composed"] is True
    assert result["die_aspect_ratio"] == "300:600"
    assert result["aspect_ratio_requested"] == "9:16"
    assert result["generated_preview"].endswith("_ai_preview.jpg")
    assert result["master"]["print_master"].endswith("_master_print.png")
    assert calls["aspect_ratio"] == "9:16"


def test_run_ai_art_pipeline_can_blank_back_panel(tmp_path, monkeypatch):
    import app.print_specs.ai_art_pipeline as pipeline

    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    out = tmp_path / "art"
    pdfs = tmp_path / "pdf"
    _write_spec(spec)
    die.write_bytes(b"%PDF fake")

    monkeypatch.setattr(pipeline, "image_generation", lambda *args, **kwargs: _png_bytes(color=(10, 20, 30)))
    monkeypatch.setattr(pipeline, "prepare_generation_references", lambda **kwargs: (kwargs["client_reference_paths"], None, None))
    monkeypatch.setattr(pipeline, "build_preflight_overlay", _fake_overlay)
    monkeypatch.setattr(pipeline, "build_safety_overlay", _fake_overlay)

    def fake_compose(**kwargs):
        kwargs["output_path"].write_bytes(kwargs["art_path"].read_bytes())
        return {"safe_composed": True}

    monkeypatch.setattr(pipeline, "compose_safe_critical_content", fake_compose)

    result = run_ai_art_pipeline(
        job_id="job_blank",
        spec_path=spec,
        die_pdf_path=die,
        client={"name": "Yeti", "phone": "1999"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "tema_fundo": "premium"},
        output_root=out,
        pdf_output_dir=pdfs,
        empty_back_panel=True,
    )

    raw = Image.open(out / "job_blank_master_raw.png").convert("RGB")
    assert result["empty_back_panel"] is True
    assert result["master"]["back_panel_treatment"]["applied"] is True
    assert raw.getpixel((150, 120)) == (255, 255, 255)
    assert raw.getpixel((150, 500)) != (255, 255, 255)


def test_run_ai_art_pipeline_promotes_first_reference_to_logo_path(tmp_path, monkeypatch):
    import app.print_specs.ai_art_pipeline as pipeline

    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    out = tmp_path / "art"
    pdfs = tmp_path / "pdf"
    logo = tmp_path / "logo.png"
    _write_spec(spec)
    die.write_bytes(b"%PDF fake")
    logo.write_bytes(_png_bytes(size=(50, 50), color=(240, 90, 20)))
    calls = {}

    def fake_image_generation(*args, **kwargs):
        return _png_bytes()

    def fake_compose(**kwargs):
        calls["edit_data"] = kwargs["edit_data"]
        kwargs["output_path"].write_bytes(kwargs["art_path"].read_bytes())
        return {"safe_composed": True}

    monkeypatch.setattr(pipeline, "image_generation", fake_image_generation)
    monkeypatch.setattr(pipeline, "prepare_generation_references", lambda **kwargs: (kwargs["client_reference_paths"], None, None))
    monkeypatch.setattr(pipeline, "build_preflight_overlay", _fake_overlay)
    monkeypatch.setattr(pipeline, "build_safety_overlay", _fake_overlay)
    monkeypatch.setattr(pipeline, "compose_safe_critical_content", fake_compose)

    run_ai_art_pipeline(
        job_id="job_logo",
        spec_path=spec,
        die_pdf_path=die,
        client={"name": "Yeti", "phone": "1999"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "tema_fundo": "premium"},
        reference_paths=[logo],
        output_root=out,
        pdf_output_dir=pdfs,
    )

    assert calls["edit_data"]["logo_path"].endswith("_logo_overlay.png")
    assert Image.open(calls["edit_data"]["logo_path"]).mode == "RGBA"
