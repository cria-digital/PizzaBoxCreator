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


def test_load_references_flattens_transparent_logo_on_white(tmp_path):
    logo = tmp_path / "logo.png"
    image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    image.putpixel((4, 4), (255, 0, 0, 255))
    image.save(logo)

    data, media_type = load_references([logo])[0]
    flattened = Image.open(io.BytesIO(data)).convert("RGB")

    assert media_type == "image/png"
    assert flattened.getpixel((0, 0)) == (255, 255, 255)
    assert flattened.getpixel((4, 4)) == (255, 0, 0)


def test_die_aspect_ratio_uses_exact_canvas():
    assert die_aspect_ratio({"canvas_px": {"width": 9713, "height": 5154}}) == "9713:5154"


def test_provider_aspect_ratio_for_die_uses_supported_nearest():
    assert provider_aspect_ratio_for_die({"canvas_px": {"width": 9713, "height": 5154}}) == "16:9"


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
    monkeypatch.setattr(pipeline, "build_preflight_overlay", lambda **kwargs: kwargs["output_path"].write_bytes(b"jpg") or kwargs["output_path"])
    monkeypatch.setattr(pipeline, "build_safety_overlay", lambda **kwargs: kwargs["output_path"].write_bytes(b"jpg") or kwargs["output_path"])
    def fake_compose(**kwargs):
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
    assert result["die_aspect_ratio"] == "600:300"
    assert result["aspect_ratio_requested"] == "16:9"
    assert result["generated_preview"].endswith("_ai_preview.jpg")
    assert calls["aspect_ratio"] == "16:9"
