from __future__ import annotations

from PIL import Image, ImageDraw

from app.print_specs.safe_composer import PixelBox, _lockup_box_within_safe_area, find_safe_boxes


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
    assert lockup.width <= round(9713 * 0.26)
    assert lockup.height <= round(5154 * 0.18)
    assert safe.left <= lockup.left < lockup.right <= safe.right
    assert safe.top <= lockup.top < lockup.bottom <= safe.bottom
