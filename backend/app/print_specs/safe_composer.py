"""Deterministic placement of critical brand/contact content inside die-safe areas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat

from app.print_specs.layout_template import print_canvas_px, rotate_print_to_design, template_zone
from app.print_specs.preflight import load_die_spec, render_die_to_bleed_box


@dataclass(frozen=True)
class PixelBox:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def area(self) -> int:
        return self.width * self.height

    def inset(self, margin: int) -> "PixelBox":
        return PixelBox(
            self.left + margin,
            self.top + margin,
            self.right - margin,
            self.bottom - margin,
        )


def unsafe_mask_from_die(
    *,
    die_pdf_path: Path,
    spec_path: Path,
    target_size: tuple[int, int],
    thicken: int = 55,
) -> Image.Image:
    """Return an L mask where cut/fold/technical neighborhoods are unsafe."""
    spec = load_die_spec(spec_path)
    die = render_die_to_bleed_box(die_pdf_path, spec, target_size).convert("RGB")
    diff = ImageChops.difference(die, Image.new("RGB", die.size, "white")).convert("L")
    mask = diff.point(lambda px: 255 if px > 12 else 0)
    if thicken > 1:
        if thicken % 2 == 0:
            thicken += 1
        mask = mask.filter(ImageFilter.MaxFilter(thicken))
    return mask


def _unsafe_mask_for_art(
    *,
    die_pdf_path: Path,
    spec_path: Path,
    art_size: tuple[int, int],
    analysis_size: tuple[int, int],
    thicken: int,
) -> Image.Image:
    spec = load_die_spec(spec_path)
    print_canvas = print_canvas_px(spec)
    is_design_rotated = (
        art_size[0] == print_canvas["height"]
        and art_size[1] == print_canvas["width"]
        and print_canvas["width"] != print_canvas["height"]
    )
    if not is_design_rotated:
        return unsafe_mask_from_die(
            die_pdf_path=die_pdf_path,
            spec_path=spec_path,
            target_size=analysis_size,
            thicken=thicken,
        )

    print_mask = unsafe_mask_from_die(
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        target_size=(analysis_size[1], analysis_size[0]),
        thicken=thicken,
    )
    return rotate_print_to_design(print_mask, spec)


def find_safe_boxes(
    mask: Image.Image,
    *,
    count: int = 3,
    cols: int = 96,
    rows: int = 54,
    min_clear_fraction: float = 0.995,
    padding_cells: int = 1,
) -> list[PixelBox]:
    """Find large rectangles that do not intersect the expanded die-line mask."""
    grid = _safe_grid(mask, cols=cols, rows=rows, min_clear_fraction=min_clear_fraction)
    boxes: list[PixelBox] = []
    for _ in range(count):
        rect = _largest_true_rectangle(grid)
        if rect is None:
            break
        left, top, right, bottom = rect
        box = _grid_rect_to_pixels(rect, mask.size, cols, rows).inset(max(4, mask.width // 120))
        if box.width > 0 and box.height > 0:
            boxes.append(box)
        for r in range(max(0, top - padding_cells), min(rows, bottom + padding_cells)):
            for c in range(max(0, left - padding_cells), min(cols, right + padding_cells)):
                grid[r][c] = False
    return boxes


def compose_safe_critical_content(
    *,
    art_path: Path,
    die_pdf_path: Path,
    spec_path: Path,
    output_path: Path,
    client: dict,
    edit_data: dict,
) -> dict:
    """Place brand, slogan and contact text in fixed template zones when safe."""
    art = Image.open(art_path).convert("RGB")
    analysis_size = _analysis_size(art.size)
    mask = _unsafe_mask_for_art(
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        art_size=art.size,
        analysis_size=analysis_size,
        thicken=max(25, analysis_size[0] // 55),
    )
    fixed_boxes = _fixed_content_boxes(art.size)
    fixed_safe = _fixed_boxes_are_safe(fixed_boxes, mask, art.size)
    if fixed_safe["usable"]:
        art = _draw_fixed_template_content(art, fixed_boxes, client, edit_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        art.save(output_path, "PNG", compress_level=1)
        return {
            "safe_composed": True,
            "method": "fixed_template_zones",
            "template": "pizza_box_standard_01",
            "logo_box": fixed_boxes["logo"].__dict__,
            "contact_box": fixed_boxes["contact_information"].__dict__,
            "fixed_zone_safety": fixed_safe,
        }

    boxes = [_scale_box(box, analysis_size, art.size) for box in find_safe_boxes(mask)]
    if not boxes:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        art.save(output_path, "PNG", compress_level=1)
        return {"safe_composed": False, "reason": "nenhuma area segura encontrada", "boxes": []}

    safe_box = _choose_brand_box(boxes, art)
    brand_box = _lockup_box_within_safe_area(safe_box, art.size)
    art = _draw_brand_lockup(art, brand_box, client, edit_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    art.save(output_path, "PNG", compress_level=1)
    return {
        "safe_composed": True,
        "method": "auto_safe_fallback",
        "fixed_zone_safety": fixed_safe,
        "safe_box": safe_box.__dict__,
        "brand_box": brand_box.__dict__,
        "boxes": [b.__dict__ for b in boxes],
    }


def _safe_grid(mask: Image.Image, *, cols: int, rows: int, min_clear_fraction: float) -> list[list[bool]]:
    w, h = mask.size
    grid: list[list[bool]] = []
    for row in range(rows):
        y0 = round(row * h / rows)
        y1 = round((row + 1) * h / rows)
        values: list[bool] = []
        for col in range(cols):
            x0 = round(col * w / cols)
            x1 = round((col + 1) * w / cols)
            crop = mask.crop((x0, y0, x1, y1))
            hist = crop.histogram()
            unsafe = sum(hist[1:])
            total = max(1, crop.width * crop.height)
            values.append((1 - unsafe / total) >= min_clear_fraction)
        grid.append(values)
    return grid


def _analysis_size(size: tuple[int, int], *, max_width: int = 1800) -> tuple[int, int]:
    width, height = size
    if width <= max_width:
        return size
    return max_width, round(max_width * height / width)


def _scale_box(box: PixelBox, source_size: tuple[int, int], target_size: tuple[int, int]) -> PixelBox:
    sx = target_size[0] / source_size[0]
    sy = target_size[1] / source_size[1]
    return PixelBox(
        round(box.left * sx),
        round(box.top * sy),
        round(box.right * sx),
        round(box.bottom * sy),
    )


def _fixed_content_boxes(canvas_size: tuple[int, int]) -> dict[str, PixelBox]:
    return {
        "logo": _normalized_zone_to_pixels(template_zone("logo"), canvas_size),
        "contact_information": _normalized_zone_to_pixels(template_zone("contact_information"), canvas_size),
    }


def _normalized_zone_to_pixels(zone, canvas_size: tuple[int, int]) -> PixelBox:
    width, height = canvas_size
    return PixelBox(
        round(zone.x_min * width),
        round(zone.y_min * height),
        round(zone.x_max * width),
        round(zone.y_max * height),
    )


def _fixed_boxes_are_safe(
    boxes: dict[str, PixelBox],
    mask: Image.Image,
    canvas_size: tuple[int, int],
    *,
    max_unsafe_fraction: float = 0.015,
) -> dict:
    ratios = {
        name: round(_unsafe_fraction(mask, _scale_box(box, canvas_size, mask.size)), 5)
        for name, box in boxes.items()
    }
    return {
        "usable": all(value <= max_unsafe_fraction for value in ratios.values()),
        "max_unsafe_fraction": max_unsafe_fraction,
        "unsafe_fraction": ratios,
    }


def _unsafe_fraction(mask: Image.Image, box: PixelBox) -> float:
    bounded = PixelBox(
        max(0, box.left),
        max(0, box.top),
        min(mask.width, box.right),
        min(mask.height, box.bottom),
    )
    if bounded.width <= 0 or bounded.height <= 0:
        return 1.0
    crop = mask.crop((bounded.left, bounded.top, bounded.right, bounded.bottom))
    hist = crop.histogram()
    unsafe = sum(hist[1:])
    return unsafe / max(1, bounded.width * bounded.height)


def _largest_true_rectangle(grid: list[list[bool]]) -> tuple[int, int, int, int] | None:
    if not grid or not grid[0]:
        return None
    cols = len(grid[0])
    heights = [0] * cols
    best: tuple[int, int, int, int] | None = None
    best_area = 0

    for row, values in enumerate(grid):
        for col, value in enumerate(values):
            heights[col] = heights[col] + 1 if value else 0
        stack: list[int] = []
        for col in range(cols + 1):
            current = heights[col] if col < cols else 0
            while stack and current < heights[stack[-1]]:
                height = heights[stack.pop()]
                left = stack[-1] + 1 if stack else 0
                width = col - left
                area = width * height
                if area > best_area:
                    best_area = area
                    best = (left, row - height + 1, col, row + 1)
            stack.append(col)
    return best


def _grid_rect_to_pixels(
    rect: tuple[int, int, int, int],
    size: tuple[int, int],
    cols: int,
    rows: int,
) -> PixelBox:
    left, top, right, bottom = rect
    w, h = size
    return PixelBox(
        round(left * w / cols),
        round(top * h / rows),
        round(right * w / cols),
        round(bottom * h / rows),
    )


def _choose_brand_box(boxes: list[PixelBox], art: Image.Image) -> PixelBox:
    size = art.size
    center_x = size[0] / 2
    center_y = size[1] / 2

    def score(box: PixelBox) -> float:
        bx = (box.left + box.right) / 2
        by = (box.top + box.bottom) / 2
        distance = abs(bx - center_x) / size[0] + abs(by - center_y) / size[1]
        shape_bonus = min(box.width / max(1, box.height), 3.0)
        visual_bonus = _quiet_dark_bonus(art, box)
        return box.area * (1.2 - distance) * shape_bonus * visual_bonus

    return max(boxes, key=score)


def _quiet_dark_bonus(art: Image.Image, box: PixelBox) -> float:
    sample = art.crop((box.left, box.top, box.right, box.bottom)).resize((80, 40), Image.Resampling.BOX)
    stat = ImageStat.Stat(sample.convert("L"))
    mean = stat.mean[0]
    stddev = stat.stddev[0]
    darkness = max(0.25, 1.45 - mean / 145)
    quietness = max(0.25, 1.35 - stddev / 55)
    return darkness * quietness


def _lockup_box_within_safe_area(safe_box: PixelBox, canvas_size: tuple[int, int]) -> PixelBox:
    canvas_w, canvas_h = canvas_size
    guard = max(28, min(canvas_w, canvas_h) // 70)
    guarded = safe_box.inset(min(guard, max(0, safe_box.width // 6), max(0, safe_box.height // 6)))
    if guarded.width > 0 and guarded.height > 0:
        safe_box = guarded

    max_w = round(canvas_w * 0.32)
    max_h = round(canvas_h * 0.20)
    target_w = min(round(safe_box.width * 0.70), max_w)
    target_h = min(round(safe_box.height * 0.34), max_h)

    aspect = target_w / max(1, target_h)
    if aspect < 1.7:
        target_h = round(target_w / 1.9)
    elif aspect > 3.4:
        target_w = round(target_h * 2.8)

    target_w = min(max(360, target_w), safe_box.width)
    target_h = min(max(180, target_h), safe_box.height)

    x = safe_box.left + (safe_box.width - target_w) // 2
    y = safe_box.top + (safe_box.height - target_h) // 2
    return PixelBox(x, y, x + target_w, y + target_h)


def _draw_fixed_template_content(
    art: Image.Image,
    boxes: dict[str, PixelBox],
    client: dict,
    edit_data: dict,
) -> Image.Image:
    base = art.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    logo = _load_logo_mark(edit_data.get("logo_path"))
    if logo is not None:
        _draw_logo_zone(overlay, logo, boxes["logo"])
    _draw_contact_zone(overlay, base, boxes["contact_information"], client, edit_data, has_logo=logo is not None)
    return Image.alpha_composite(base, overlay).convert("RGB")


def _draw_logo_zone(overlay: Image.Image, logo: Image.Image, box: PixelBox) -> None:
    pad = max(10, min(box.width, box.height) // 10)
    content = box.inset(pad)
    if content.width <= 0 or content.height <= 0:
        return
    image = ImageOps.contain(
        logo.convert("RGBA"),
        (content.width, content.height),
        method=Image.Resampling.LANCZOS,
    )
    x = content.left + (content.width - image.width) // 2
    y = content.top + (content.height - image.height) // 2
    overlay.alpha_composite(image, (x, y))


def _draw_contact_zone(
    overlay: Image.Image,
    base: Image.Image,
    box: PixelBox,
    client: dict,
    edit_data: dict,
    *,
    has_logo: bool,
) -> None:
    brand = client.get("name") or "Pizzaria"
    slogan = edit_data.get("frase") or ""
    phone = edit_data.get("telefone") or client.get("phone") or ""
    instagram = edit_data.get("instagram") or client.get("instagram") or ""
    items = _contact_items(phone=phone, instagram=instagram)

    text_lines: list[str] = []
    if not has_logo and brand:
        text_lines.append(brand)
    if slogan:
        text_lines.append(slogan)
    if not text_lines and not items:
        return

    draw = ImageDraw.Draw(overlay)
    pad = max(10, min(box.width, box.height) // 8)
    content = box.inset(pad)
    if content.width <= 0 or content.height <= 0:
        return

    palette = _readability_palette(base, box)
    accent = palette["accent"]
    text_fill = palette["text"]
    support_fill = palette["support"]

    slogan_font = _fit_font(slogan or brand, content.width, max(18, content.height // 3))
    brand_font = _fit_font(brand, content.width, max(20, content.height // 3))
    item_font = _fit_font("  ".join(text for _, text in items) or "contato", content.width, max(12, content.height // 5))
    gap = max(7, content.height // 13)
    rows: list[tuple[str, int]] = []
    if not has_logo and brand:
        rows.append(("brand", _text_size(draw, brand, brand_font)[1]))
    if slogan:
        rows.append(("slogan", _text_size(draw, slogan, slogan_font)[1]))
    if items:
        rows.append(("items", max(item_font.size + max(10, item_font.size // 2), content.height // 4)))
    total_h = sum(height for _, height in rows) + gap * max(0, len(rows) - 1)
    y = content.top + max(0, (content.height - total_h) // 2)

    if not has_logo and brand:
        y = _draw_centered_text(draw, brand, brand_font, content, y, fill=text_fill, shadow=palette["shadow"]) + gap
    if slogan:
        y = _draw_display_slogan(draw, slogan, slogan_font, content, y, fill=text_fill, accent=accent) + gap
    if items:
        _draw_contact_items(draw, items, item_font, content, y, text_fill=text_fill, support_fill=support_fill, accent=accent)


def _contact_items(*, phone: str, instagram: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if phone:
        items.append(("phone", phone))
    if instagram:
        items.append(("instagram", instagram))
    return items


def _readability_palette(base: Image.Image, box: PixelBox) -> dict[str, tuple[int, int, int, int]]:
    crop = base.crop((box.left, box.top, box.right, box.bottom)).resize((80, 40), Image.Resampling.BOX)
    stat = ImageStat.Stat(crop.convert("L"))
    mean = stat.mean[0]
    if mean < 132:
        return {
            "text": (255, 246, 224, 255),
            "support": (12, 16, 22, 122),
            "accent": (255, 138, 42, 235),
            "shadow": (0, 0, 0, 120),
        }
    return {
        "text": (32, 24, 18, 255),
        "support": (255, 248, 232, 142),
        "accent": (169, 54, 35, 235),
        "shadow": (255, 255, 255, 95),
    }


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    content: PixelBox,
    y: int,
    *,
    fill: tuple[int, int, int, int],
    shadow: tuple[int, int, int, int],
) -> int:
    text_w, text_h = _text_size(draw, text, font)
    x = content.left + max(0, (content.width - text_w) // 2)
    draw.text((x + 1, y + 1), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    return y + text_h


def _draw_display_slogan(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    content: PixelBox,
    y: int,
    *,
    fill: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
) -> int:
    text_w, text_h = _text_size(draw, text, font)
    x = content.left + max(0, (content.width - text_w) // 2)
    underline_y = y + text_h + max(4, font.size // 8)
    ornament_w = min(content.width, max(text_w, content.width // 3))
    ornament_x = content.left + (content.width - ornament_w) // 2
    draw.line((ornament_x, underline_y, ornament_x + ornament_w, underline_y), fill=accent, width=max(2, font.size // 11))
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 85))
    draw.text((x, y), text, font=font, fill=fill)
    return underline_y + max(2, font.size // 14)


def _draw_contact_items(
    draw: ImageDraw.ImageDraw,
    items: list[tuple[str, str]],
    font: ImageFont.ImageFont,
    content: PixelBox,
    y: int,
    *,
    text_fill: tuple[int, int, int, int],
    support_fill: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
) -> None:
    icon_size = max(12, round(font.size * 1.1))
    gap = max(10, font.size // 2)
    item_sizes = [_contact_item_size(draw, text, font, icon_size) for _, text in items]
    total_w = sum(width for width, _ in item_sizes) + gap * max(0, len(items) - 1)
    if total_w <= content.width:
        x = content.left + (content.width - total_w) // 2
        for (kind, text), (item_w, item_h) in zip(items, item_sizes):
            _draw_contact_item(draw, kind, text, font, x, y, icon_size, item_h, text_fill=text_fill, support_fill=support_fill, accent=accent)
            x += item_w + gap
        return

    row_h = max(height for _, height in item_sizes)
    total_h = row_h * len(items) + max(4, font.size // 4) * (len(items) - 1)
    y = y + max(0, (content.bottom - y - total_h) // 2)
    for kind, text in items:
        item_w, item_h = _contact_item_size(draw, text, font, icon_size)
        x = content.left + max(0, (content.width - item_w) // 2)
        _draw_contact_item(draw, kind, text, font, x, y, icon_size, item_h, text_fill=text_fill, support_fill=support_fill, accent=accent)
        y += row_h + max(4, font.size // 4)


def _contact_item_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    icon_size: int,
) -> tuple[int, int]:
    text_w, text_h = _text_size(draw, text, font)
    pad_x = max(8, icon_size // 2)
    pad_y = max(5, icon_size // 4)
    return icon_size + max(6, icon_size // 3) + text_w + pad_x * 2, max(icon_size, text_h) + pad_y * 2


def _draw_contact_item(
    draw: ImageDraw.ImageDraw,
    kind: str,
    text: str,
    font: ImageFont.ImageFont,
    x: int,
    y: int,
    icon_size: int,
    row_h: int,
    *,
    text_fill: tuple[int, int, int, int],
    support_fill: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
) -> None:
    radius = max(6, row_h // 3)
    width, _ = _contact_item_size(draw, text, font, icon_size)
    draw.rounded_rectangle((x, y, x + width, y + row_h), radius=radius, fill=support_fill)
    icon_x = x + max(8, icon_size // 2)
    icon_y = y + (row_h - icon_size) // 2
    _draw_contact_icon(draw, kind, icon_x, icon_y, icon_size, accent)
    text_x = icon_x + icon_size + max(6, icon_size // 3)
    text_y = y + (row_h - _text_size(draw, text, font)[1]) // 2
    draw.text((text_x + 1, text_y + 1), text, font=font, fill=(0, 0, 0, 80))
    draw.text((text_x, text_y), text, font=font, fill=text_fill)


def _draw_contact_icon(
    draw: ImageDraw.ImageDraw,
    kind: str,
    x: int,
    y: int,
    size: int,
    fill: tuple[int, int, int, int],
) -> None:
    width = max(2, size // 9)
    if kind == "instagram":
        radius = max(3, size // 5)
        draw.rounded_rectangle((x, y, x + size, y + size), radius=radius, outline=fill, width=width)
        inset = max(4, size // 3)
        draw.ellipse((x + inset, y + inset, x + size - inset, y + size - inset), outline=fill, width=width)
        dot = max(2, size // 8)
        draw.ellipse((x + size - dot * 3, y + dot * 2, x + size - dot, y + dot * 4), fill=fill)
        return
    if kind == "phone":
        draw.arc((x + size * 0.10, y + size * 0.05, x + size * 0.85, y + size * 0.90), 125, 235, fill=fill, width=width)
        draw.line((x + size * 0.28, y + size * 0.75, x + size * 0.42, y + size * 0.88), fill=fill, width=width)
        draw.line((x + size * 0.62, y + size * 0.14, x + size * 0.78, y + size * 0.26), fill=fill, width=width)
        return
    draw.ellipse((x, y, x + size, y + size), outline=fill, width=width)


def _draw_brand_lockup(art: Image.Image, box: PixelBox, client: dict, edit_data: dict) -> Image.Image:
    brand = client.get("name") or "Pizzaria"
    slogan = edit_data.get("frase") or "Sua pizza chegou!"
    phone = edit_data.get("telefone") or client.get("phone") or ""
    instagram = edit_data.get("instagram") or client.get("instagram") or ""
    contact = "  ".join(part for part in [phone, instagram] if part)
    logo = _load_logo_mark(edit_data.get("logo_path"))

    base = art.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pad = max(14, min(box.width, box.height) // 11)
    content = box.inset(pad)
    accent_w = max(3, min(box.width, box.height) // 65)
    ornament_y_top = content.top
    ornament_y_bottom = content.bottom
    draw.line((content.left, ornament_y_top, content.right, ornament_y_top), fill=(255, 120, 28, 210), width=accent_w)
    draw.line((content.left, ornament_y_bottom, content.right, ornament_y_bottom), fill=(22, 100, 60, 210), width=accent_w)

    logo_size = 0
    logo_gap = max(18, content.width // 22)
    if logo is not None and content.width >= content.height * 1.7:
        logo_size = min(round(content.height * 0.78), round(content.width * 0.24))
    text_left = content.left + logo_size + (logo_gap if logo_size else 0)
    text_width = max(120, content.right - text_left)

    brand_font = _fit_font(brand, text_width, max(24, content.height // 3))
    slogan_font = _fit_font(slogan, text_width, max(15, content.height // 7))
    contact_font = _fit_font(contact, text_width, max(12, content.height // 10)) if contact else None

    lines = [(brand, brand_font, (255, 244, 210))]
    if slogan:
        lines.append((slogan, slogan_font, (255, 255, 255)))
    if contact and contact_font:
        lines.append((contact, contact_font, (245, 245, 245)))

    heights = [_text_size(draw, text, font)[1] for text, font, _ in lines]
    gap = max(8, content.height // 18)
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = content.top + max(0, (content.height - total_h) // 2)

    if logo is not None and logo_size:
        mark = _prepare_logo_mark(logo, logo_size)
        logo_y = content.top + (content.height - logo_size) // 2
        overlay.alpha_composite(mark, (content.left, logo_y))

    for (text, font, fill), text_h in zip(lines, heights):
        text_w, _ = _text_size(draw, text, font)
        x = text_left if logo_size else content.left + max(0, (content.width - text_w) // 2)
        stroke = max(2, font.size // 14)
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 215))
        y += text_h + gap

    return Image.alpha_composite(base, overlay).convert("RGB")


def _load_logo_mark(path: str | None) -> Image.Image | None:
    if not path:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _prepare_logo_mark(logo: Image.Image, size: int) -> Image.Image:
    image = ImageOps.contain(logo.convert("RGBA"), (size, size), method=Image.Resampling.LANCZOS)
    mark = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    return mark


def _fit_font(text: str, max_width: int, max_size: int) -> ImageFont.FreeTypeFont:
    text = text or " "
    for size in range(max_size, 9, -2):
        font = _font(size)
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _font(10)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]
