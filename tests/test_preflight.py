from __future__ import annotations

import json

from PIL import Image

from app.print_specs.preflight import (
    bleed_crop_box_for_rendered_media,
    fit_image_to_canvas,
    line_art_overlay,
    load_die_spec,
)


def _spec() -> dict:
    return {
        "page": 1,
        "aspect_ratio": 2.0,
        "canvas_px": {"width": 800, "height": 400},
        "boxes": {
            "MediaBox": {
                "points": {
                    "left": -45,
                    "bottom": -45,
                    "right": 855,
                    "top": 455,
                    "width": 900,
                    "height": 500,
                }
            },
            "BleedBox": {
                "points": {
                    "left": 0,
                    "bottom": 0,
                    "right": 800,
                    "top": 400,
                    "width": 800,
                    "height": 400,
                }
            },
        },
    }


def test_bleed_crop_box_converts_pdf_origin_to_image_origin():
    assert bleed_crop_box_for_rendered_media(_spec(), (900, 500)) == (45, 55, 845, 455)


def test_fit_image_to_canvas_cover_and_contain():
    source = Image.new("RGB", (100, 100), "red")

    cover = fit_image_to_canvas(source, {"width": 200, "height": 100}, mode="cover")
    contain = fit_image_to_canvas(source, {"width": 200, "height": 100}, mode="contain")

    assert cover.size == (200, 100)
    assert contain.size == (200, 100)
    assert contain.getpixel((0, 0)) == (255, 255, 255)
    assert contain.getpixel((100, 50)) == (255, 0, 0)


def test_line_art_overlay_masks_non_white_pixels():
    die = Image.new("RGB", (20, 20), "white")
    for y in range(20):
        die.putpixel((10, y), (0, 200, 255))

    overlay = line_art_overlay(die, thicken=1)
    assert overlay.getpixel((10, 10))[3] > 0
    assert overlay.getpixel((0, 0))[3] == 0


def test_load_die_spec_reads_json(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(_spec()), encoding="utf-8")

    assert load_die_spec(path)["canvas_px"] == {"width": 800, "height": 400}

