from __future__ import annotations

import json

from PIL import Image

from app.ai.box_designer import PizzaBoxTextAgent, build_box_prompt
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

    assert "1.8846" not in prompt
    assert "5154x9713" not in prompt
    assert "9713x5154" not in prompt
    assert "x 0." not in prompt
    assert "y 0." not in prompt
    assert "faca" in prompt
    assert "full-bleed" in prompt
    assert "mockup" in prompt
    assert "Nao gere divisorias artificiais" in prompt
    assert "3% da altura" not in prompt
    assert "Priorize contraste" in prompt
    assert "sangria" in prompt
    assert "Como nao existem referencias visuais adicionais" in prompt


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
    assert "referencias visuais do cliente" in prompt
    assert "Nao redesenhe o logotipo" in prompt


def test_build_box_prompt_can_defer_critical_content_to_code():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "instagram": "@yeti"},
        critical_content_by_code=True,
    )

    assert "DIRECAO VISUAL DO CLIENTE" in prompt
    assert "Nome: Yeti" not in prompt
    assert "Telefone: 1999" not in prompt
    assert "Instagram: @yeti" not in prompt
    assert "nenhum telefone" in prompt
    assert "logotipo oficial" in prompt
    assert "PIPELINE DE COMPOSICAO" in prompt


def test_build_box_prompt_can_request_empty_back_panel_without_coordinates():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "empty_back_panel": True},
        critical_content_by_code=True,
    )

    assert "TRATAMENTO DO VERSO" in prompt
    assert "parte de tras/parte de baixo da caixa vazia" in prompt
    assert "x 0." not in prompt
    assert "y 0." not in prompt


def test_build_box_prompt_uses_reference_as_style_not_generated_logo():
    prompt = build_box_prompt(
        client={"name": "Yeti"},
        template={"product_type": "pizza"},
        edit_data={"telefone": "1999", "instagram": "@yeti"},
        has_client_references=True,
        critical_content_by_code=True,
    )

    assert "somente linguagem visual" in prompt
    assert "As demais imagens anexadas sao referencias visuais do cliente" in prompt
    assert "Nao redesenhe o logotipo" in prompt
    assert "Nao coloque a imagem de referencia inteira dentro" in prompt
    assert "NAO escreva o nome da pizzaria" in prompt


def test_pizza_box_text_agent_guides_image_agent_for_print_and_cutlines():
    prompt = PizzaBoxTextAgent(
        client={"name": "Borcelle", "phone": "(11) 99999-9999", "instagram": "@borcelle"},
        template={"product_type": "pizza"},
        edit_data={"frase": "Desde 2012", "tema_fundo": "premium"},
        die_spec={
            "aspect_ratio": 1.8846,
            "canvas_px": {"width": 9713, "height": 5154},
            "bleed_mm": {"left": 3.17, "right": 3.17, "top": 3.17, "bottom": 3.17},
            "prompt_constraints": {"must_not_draw": ["faca", "linha de corte", "vinco"]},
        },
        has_die_guide=True,
        has_client_references=True,
        critical_content_by_code=True,
    ).build_image_prompt()

    assert "DIRETOR DE ARTE" in prompt
    assert "DESIGNER GRAFICO SENIOR" in prompt
    assert "Crie exclusivamente a ARTE VISUAL PLANIFICADA" in prompt
    assert "Nome: Borcelle" not in prompt
    assert "Telefone: (11) 99999-9999" not in prompt
    assert "Instagram: @borcelle" not in prompt
    assert "Observe cortes, vincos, dobras" in prompt
    assert "cortes, vincos, dobras" in prompt
    assert "paleta coerente" in prompt
    assert "impressao em papelao" in prompt
    assert "Zona fixa do logo" not in prompt
    assert "Zona fixa de contato" not in prompt
    assert "coordenada" in prompt
    assert "nenhum valor X ou Y" in prompt
