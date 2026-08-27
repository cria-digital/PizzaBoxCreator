from __future__ import annotations

import json

from PIL import Image

from app.ai.box_designer import build_box_prompt
from app.print_specs.art_master import (
    build_art_master,
    cover_light_edge_leaks,
    save_approval_preview,
    trim_generated_mockup_margin,
)


def _write_spec(path):
    spec = {
        "dpi": 300,
        "canvas_px": {"width": 400, "height": 200},
        "bleed_size_mm": {"width": 100, "height": 50},
        "trim_size_mm": {"width": 96, "height": 46},
        "aspect_ratio": 2.0,
        "prompt_constraints": {
            "must_not_draw": ["faca", "linha de corte", "vinco"],
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")


def test_build_art_master_outputs_exact_canvas_and_metadata(tmp_path):
    source = tmp_path / "source.png"
    spec = tmp_path / "spec.json"
    master = tmp_path / "master.png"
    preview = tmp_path / "preview.jpg"
    Image.new("RGB", (100, 100), "red").save(source)
    _write_spec(spec)

    result = build_art_master(
        source_path=source,
        spec_path=spec,
        output_path=master,
        preview_path=preview,
        fit_mode="cover",
    )

    assert Image.open(master).size == (400, 200)
    assert Image.open(preview).size == (400, 200)
    assert result["canvas_px"] == {"width": 400, "height": 200}
    assert json.loads(master.with_suffix(".json").read_text())["master"] == str(master)


def test_build_art_master_can_trim_generated_mockup_margin(tmp_path):
    source = tmp_path / "source.png"
    spec = tmp_path / "spec.json"
    master = tmp_path / "master.png"
    image = Image.new("RGB", (500, 300), (174, 177, 186))
    for x in range(60, 440):
        for y in range(45, 255):
            image.putpixel((x, y), (210, 20, 20) if x < 250 else (20, 30, 160))
    image.save(source)
    _write_spec(spec)

    result = build_art_master(
        source_path=source,
        spec_path=spec,
        output_path=master,
        fit_mode="stretch",
        auto_trim_mockup_margin=True,
    )
    output = Image.open(master).convert("RGB")

    assert output.size == (400, 200)
    assert result["margin_trim"]["trimmed"] is True
    assert result["fitted_source_px"]["width"] < result["source_px"]["width"]
    assert output.getpixel((4, 4)) != (174, 177, 186)


def test_trim_generated_mockup_margin_ignores_full_bleed_art():
    image = Image.new("RGB", (400, 200), "red")

    trimmed, info = trim_generated_mockup_margin(image)

    assert trimmed.size == image.size
    assert info["trimmed"] is False


def test_cover_light_edge_leaks_fills_bright_corner_only():
    image = Image.new("RGB", (120, 80), (12, 20, 32))
    for x in range(0, 22):
        for y in range(0, 24):
            image.putpixel((x, y), (238, 238, 240))
    image.putpixel((70, 40), (238, 238, 240))

    repaired, info = cover_light_edge_leaks(image)

    assert info["applied"] is True
    assert repaired.getpixel((5, 5)) != (238, 238, 240)
    assert repaired.getpixel((70, 40)) == (238, 238, 240)


def test_cover_light_edge_leaks_fills_light_gray_border():
    image = Image.new("RGB", (160, 90), (18, 22, 33))
    for y in range(0, 14):
        for x in range(0, 160):
            image.putpixel((x, y), (196, 198, 203))

    repaired, info = cover_light_edge_leaks(image)

    assert info["applied"] is True
    assert repaired.getpixel((80, 4)) != (196, 198, 203)


def test_build_art_master_can_cover_light_edge_leaks(tmp_path):
    source = tmp_path / "source.png"
    spec = tmp_path / "spec.json"
    master = tmp_path / "master.png"
    image = Image.new("RGB", (400, 200), (15, 20, 32))
    for x in range(0, 40):
        for y in range(0, 50):
            image.putpixel((x, y), (238, 238, 240))
    image.save(source)
    _write_spec(spec)

    result = build_art_master(
        source_path=source,
        spec_path=spec,
        output_path=master,
        fit_mode="stretch",
        cover_edge_leaks=True,
    )

    assert result["edge_leak_repair"]["applied"] is True
    assert Image.open(master).convert("RGB").getpixel((4, 4)) != (238, 238, 240)


def test_save_approval_preview_respects_max_width(tmp_path):
    output = tmp_path / "preview.jpg"
    master = Image.new("RGB", (1000, 500), "blue")

    save_approval_preview(master, output, max_width=200, watermark="")

    assert Image.open(output).size == (200, 100)


def test_build_box_prompt_accepts_die_spec_constraints():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999"},
        die_spec={
            "aspect_ratio": 1.8846,
            "canvas_px": {"width": 9713, "height": 5154},
            "prompt_constraints": {"must_not_draw": ["faca", "linha de corte"]},
        },
    )

    assert "1.8846" in prompt
    assert "9713x5154" in prompt
    assert "faca" in prompt
    assert "full-bleed" in prompt
    assert "sem mockup" in prompt
    assert "sem divisorias internas" in prompt
    assert "Como nao ha imagem de referencia" in prompt


def test_build_box_prompt_prioritizes_client_reference():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999"},
        die_spec={
            "aspect_ratio": 1.8846,
            "canvas_px": {"width": 9713, "height": 5154},
            "prompt_constraints": {"must_not_draw": ["faca", "linha de corte"]},
        },
        has_die_guide=True,
        has_client_references=True,
    )

    assert "primeira imagem anexada e um GUIA TECNICO" in prompt
    assert "referencias do cliente" in prompt
    assert "Nao invente um logo diferente" in prompt


def test_build_box_prompt_can_defer_critical_content_to_code():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "instagram": "@yeti"},
        critical_content_by_code=True,
    )

    assert "Nao escreva nenhum texto real" in prompt
    assert "qualquer bloco de informacao" in prompt
    assert "adicionados depois por software" in prompt
    assert "Yeti" not in prompt
    assert "@yeti" not in prompt


def test_build_box_prompt_does_not_copy_reference_text_when_code_places_content():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "instagram": "@yeti"},
        has_client_references=True,
        critical_content_by_code=True,
    )

    assert "Nao copie textos" in prompt
    assert "identidade visual principal" in prompt
    assert "personagem ou logo" in prompt
    assert "preserve identidade" not in prompt
