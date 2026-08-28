from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from app.print_specs.safe_composer import (
    PixelBox,
    _choose_brand_box,
    _draw_fixed_template_content,
    _draw_brand_lockup,
    _fixed_boxes_are_safe,
    _fixed_content_boxes,
    _lockup_box_within_safe_area,
    _prepare_logo_mark,
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


def test_fixed_template_boxes_follow_normalized_logo_zone():
    boxes = _fixed_content_boxes((1000, 2000))

    logo = boxes["logo"]
    contact = boxes["contact_information"]

    assert 180 < logo.left < 200
    assert 800 < logo.right < 820
    assert 1220 < logo.top < 1240
    assert 1500 < logo.bottom < 1510
    assert contact.top > logo.bottom


def test_fixed_template_safety_rejects_cut_intersection():
    mask = Image.new("L", (1000, 500), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((180, 300, 820, 390), fill=255)
    boxes = _fixed_content_boxes((1000, 500))

    safety = _fixed_boxes_are_safe(boxes, mask, (1000, 500))

    assert safety["usable"] is False
    assert safety["unsafe_fraction"]["logo"] > 0


def test_draw_fixed_template_content_uses_uploaded_logo_and_contact(tmp_path):
    art = Image.new("RGB", (1000, 500), (18, 22, 34))
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (180, 80), (240, 90, 20, 255)).save(logo)
    boxes = _fixed_content_boxes(art.size)

    result = _draw_fixed_template_content(
        art,
        boxes,
        {"name": "Pizzaria Goku"},
        {"telefone": "(11) 99999-9999", "instagram": "@goku", "frase": "Sua pizza chegou!", "logo_path": str(logo)},
    )

    logo_box = boxes["logo"]
    contact_box = boxes["contact_information"]
    assert ImageChops.difference(
        art.crop((logo_box.left, logo_box.top, logo_box.right, logo_box.bottom)),
        result.crop((logo_box.left, logo_box.top, logo_box.right, logo_box.bottom)),
    ).getbbox() is not None
    assert result.getpixel(((contact_box.left + contact_box.right) // 2, (contact_box.top + contact_box.bottom) // 2)) != (18, 22, 34)


def test_prepare_logo_mark_keeps_transparent_background():
    logo = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    for x in range(10, 30):
        for y in range(5, 15):
            logo.putpixel((x, y), (240, 90, 20, 255))

    mark = _prepare_logo_mark(logo, 80)

    assert mark.mode == "RGBA"
    assert mark.getpixel((0, 0))[3] == 0
