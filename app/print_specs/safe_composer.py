"""Deterministic placement of critical brand/contact content inside die-safe areas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

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
    """Place brand, slogan and contact text in the largest die-safe area."""
    art = Image.open(art_path).convert("RGB")
    analysis_size = _analysis_size(art.size)
    mask = unsafe_mask_from_die(
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        target_size=analysis_size,
        thicken=max(17, analysis_size[0] // 80),
    )
    boxes = [_scale_box(box, analysis_size, art.size) for box in find_safe_boxes(mask)]
    if not boxes:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        art.save(output_path, "PNG", compress_level=1)
        return {"safe_composed": False, "reason": "nenhuma area segura encontrada", "boxes": []}

    safe_box = _choose_brand_box(boxes, art.size)
    brand_box = _lockup_box_within_safe_area(safe_box, art.size)
    art = _draw_brand_lockup(art, brand_box, client, edit_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    art.save(output_path, "PNG", compress_level=1)
    return {
        "safe_composed": True,
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


def _choose_brand_box(boxes: list[PixelBox], size: tuple[int, int]) -> PixelBox:
    center_x = size[0] / 2
    center_y = size[1] / 2

    def score(box: PixelBox) -> float:
        bx = (box.left + box.right) / 2
        by = (box.top + box.bottom) / 2
        distance = abs(bx - center_x) / size[0] + abs(by - center_y) / size[1]
        shape_bonus = min(box.width / max(1, box.height), 3.0)
        return box.area * (1.2 - distance) * shape_bonus

    return max(boxes, key=score)


def _lockup_box_within_safe_area(safe_box: PixelBox, canvas_size: tuple[int, int]) -> PixelBox:
    canvas_w, canvas_h = canvas_size
    max_w = round(canvas_w * 0.26)
    max_h = round(canvas_h * 0.18)
    target_w = min(round(safe_box.width * 0.58), max_w)
    target_h = min(round(safe_box.height * 0.30), max_h)

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


def _draw_brand_lockup(art: Image.Image, box: PixelBox, client: dict, edit_data: dict) -> Image.Image:
    brand = client.get("name") or "Pizzaria"
    slogan = edit_data.get("frase") or "Sua pizza chegou!"
    phone = edit_data.get("telefone") or client.get("phone") or ""
    instagram = edit_data.get("instagram") or client.get("instagram") or ""
    contact = "  ".join(part for part in [phone, instagram] if part)

    base = art.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pad = max(10, min(box.width, box.height) // 14)
    content = box.inset(pad)

    brand_font = _fit_font(brand, content.width, max(20, content.height // 4))
    slogan_font = _fit_font(slogan, content.width, max(14, content.height // 7))
    contact_font = _fit_font(contact, content.width, max(12, content.height // 10)) if contact else None

    lines = [(brand, brand_font, (255, 244, 210))]
    if slogan:
        lines.append((slogan, slogan_font, (255, 255, 255)))
    if contact and contact_font:
        lines.append((contact, contact_font, (245, 245, 245)))

    heights = [_text_size(draw, text, font)[1] for text, font, _ in lines]
    gap = max(8, content.height // 18)
    total_h = sum(heights) + gap * (len(lines) - 1)
    y = content.top + max(0, (content.height - total_h) // 2)
    shadow_pad = max(14, min(box.width, box.height) // 18)
    draw.rounded_rectangle(
        (
            content.left - shadow_pad,
            y - shadow_pad,
            content.right + shadow_pad,
            y + total_h + shadow_pad,
        ),
        radius=max(16, shadow_pad),
        fill=(0, 0, 0, 72),
    )
    for (text, font, fill), text_h in zip(lines, heights):
        text_w, _ = _text_size(draw, text, font)
        x = content.left + max(0, (content.width - text_w) // 2)
        stroke = max(2, font.size // 14)
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 215))
        y += text_h + gap

    return Image.alpha_composite(base, overlay).convert("RGB")


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
