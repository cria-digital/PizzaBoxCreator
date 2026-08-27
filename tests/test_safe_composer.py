from __future__ import annotations

from PIL import Image, ImageDraw

from app.print_specs.safe_composer import (
    PixelBox,
    _choose_brand_box,
    _draw_brand_lockup,
    _lockup_box_within_safe_area,
    find_safe_boxes,
)


def test_find_safe_boxes_avoids_expanded_cut_line():
    mask = Image.new("L", (1000, 500), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((480, 0, 520, 500), fill=255)

    boxes = find_safe_boxes(mask, count=2, cols=50, rows=25)

    assert boxes
    assert all(not (box.left < 520 and box.right > 480) for box in boxes)
    assert boxes[0].width > 300


def test_lockup_box_does_not_fill_whole_safe_area():
    safe = PixelBox(1000, 500, 4100, 4300)

    lockup = _lockup_box_within_safe_area(safe, (9713, 5154))

    assert lockup.width < safe.width
    assert lockup.height < safe.height
    assert lockup.width <= round(9713 * 0.32)
    assert lockup.height <= round(5154 * 0.20)
    assert safe.left <= lockup.left < lockup.right <= safe.right
    assert safe.top <= lockup.top < lockup.bottom <= safe.bottom


def test_choose_brand_box_prefers_quiet_dark_area():
    art = Image.new("RGB", (600, 300), (20, 24, 34))
    draw = ImageDraw.Draw(art)
    draw.rectangle((0, 0, 300, 300), fill=(230, 190, 90))
    boxes = [
        PixelBox(20, 40, 280, 240),
        PixelBox(320, 40, 580, 240),
    ]

    chosen = _choose_brand_box(boxes, art)

    assert chosen.left == 320


def test_draw_brand_lockup_places_uploaded_logo(tmp_path):
    art = Image.new("RGB", (900, 420), (18, 22, 34))
    logo = tmp_path / "goku.png"
    Image.new("RGBA", (100, 100), (240, 90, 20, 255)).save(logo)
    box = PixelBox(120, 100, 650, 300)

    result = _draw_brand_lockup(
        art,
        box,
        {"name": "Pizzaria Goku"},
        {"telefone": "(11) 99999-9999", "instagram": "@goku", "frase": "Sua pizza chegou!", "logo_path": str(logo)},
    )

    assert result.getpixel((170, 155)) != (18, 22, 34)


def test_draw_brand_lockup_does_not_paint_black_card():
    art = Image.new("RGB", (900, 420), (232, 210, 178))
    box = PixelBox(120, 100, 650, 300)

    result = _draw_brand_lockup(
        art,
        box,
        {"name": "Pizzaria Goku"},
        {"telefone": "(11) 99999-9999", "instagram": "@goku", "frase": "Sua pizza chegou!"},
    )

    assert result.getpixel((135, 145)) == (232, 210, 178)
