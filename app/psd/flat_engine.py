"""Flat image engine: generates previews from a flat artwork image + calibration.

This replaces the PSD-heavy pipeline for preview generation. Instead of opening a
20–500 MB PSD, editing it, and compositing layers via PhotoshopAPI, the flat engine:

1. Loads a lightweight flat image (PNG/JPG, a few MB) — one per background variant.
2. Draws text (phone, Instagram, phrase) using Pillow at the calibrated positions.
3. Composites the client logo on top, also at calibrated positions.
4. Outputs a JPG preview in seconds.

The calibration data (from the /calibrar UI) maps each editable field to pixel
coordinates on the flat image, exactly as it does for the PSD engine.

On approval, a "production package" is delivered to the designer instead of a degraded
PSD — the flat image is the designer's original artwork, never modified by the system.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from app.config import settings
from app.models.commands import EditCommand, TemaFundo
from app.psd.calibration import layers_for_base
from app.psd.text_metrics import get_font, wrap_text

logger = logging.getLogger(__name__)

ALLOWED_LOGO_ROOTS = (settings.temp_dir, settings.logos_dir)


class FlatEngine:
    """Generate a preview from a flat artwork image + calibration + EditCommand."""

    def __init__(self, flat_image_path: Path):
        self.flat_image_path = flat_image_path
        self.canvas = Image.open(flat_image_path).convert("RGBA")
        self.width, self.height = self.canvas.size

    def apply(self, cmd: EditCommand, calibration: dict | None = None) -> list[str]:
        """Apply edit commands on top of the flat artwork. Returns list of changes."""
        calibration = calibration or {}
        changes: list[str] = []

        if cmd.telefone is not None:
            changes += self._draw_text("TEXTO_TELEFONE", cmd.telefone, calibration)

        if cmd.instagram is not None:
            changes += self._draw_text("TEXTO_INSTAGRAM", cmd.instagram, calibration)

        if cmd.frase is not None:
            changes += self._draw_text("TEXTO_FRASE_OPCIONAL", cmd.frase, calibration)

        if cmd.logo_path:
            changes += self._composite_logo(cmd.logo_path, calibration)

        return changes

    def render(self, output_path: Path, max_width: int | None = None) -> Path:
        """Flatten to RGB and save as JPEG. Returns the output path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rgb = Image.new("RGB", self.canvas.size, (255, 255, 255))
        rgb.paste(self.canvas, mask=self.canvas.split()[3])

        if max_width is None:
            max_width = settings.preview_max_width
        if rgb.width > max_width:
            ratio = max_width / rgb.width
            rgb = rgb.resize((max_width, int(rgb.height * ratio)), Image.LANCZOS)

        rgb.save(str(output_path), "JPEG", quality=settings.preview_quality)
        return output_path

    def _draw_text(self, base: str, text: str, calibration: dict) -> list[str]:
        """Draw text at calibrated positions for all faces of a field (BASE, BASE_2, ...)."""
        changes: list[str] = []
        draw = ImageDraw.Draw(self.canvas)

        # Collect all face positions for this base field.
        positions = []
        for key, box in calibration.items():
            if not isinstance(box, dict):
                continue
            key_base = key.rsplit("_", 1)[0] if key[-1].isdigit() and key[-2] == "_" else key
            # Handle names like TEXTO_TELEFONE_2
            if key.startswith(base) and (key == base or key.startswith(base + "_")):
                positions.append((key, box))

        if not positions:
            return [f"AVISO: posicao '{base}' nao encontrada na calibracao"]

        for layer_name, box in positions:
            font_size = int(box.get("font_size", 36))
            font = get_font(max(font_size, 10))
            color = (0, 0, 0)  # default text color

            x = int(box.get("x", 0))
            y = int(box.get("y", 0))
            box_width = box.get("width")
            box_height = box.get("height")

            if box_width and box_height:
                lines = wrap_text(draw, text, font, float(box_width))
                line_height = font_size * 1.2
                # Vertically center within the box
                total_text_height = len(lines) * line_height
                y_offset = max(0, (float(box_height) - total_text_height) / 2)
                for i, line in enumerate(lines):
                    draw.text((x, y + y_offset + i * line_height), line,
                              font=font, fill=color)
            else:
                draw.text((x, y), text, font=font, fill=color)

            changes.append(f"Texto '{layer_name}' desenhado: {text}")

        return changes

    def _composite_logo(self, logo_path: str, calibration: dict) -> list[str]:
        """Composite client logo at calibrated positions for all faces."""
        resolved = self._resolve_logo(logo_path)
        if resolved is None:
            return [f"AVISO: Logo nao encontrada ou caminho nao permitido: {logo_path}"]

        try:
            logo = Image.open(resolved).convert("RGBA")
        except Exception:
            return [f"AVISO: Nao foi possivel ler a logo: {resolved.name}"]

        changes: list[str] = []
        for key, box in calibration.items():
            if not isinstance(box, dict):
                continue
            if key.startswith("LOGO_CLIENTE"):
                changes += self._paste_logo(logo, key, box)

        if not changes:
            return ["AVISO: Posicao 'LOGO_CLIENTE' nao encontrada na calibracao"]

        return changes

    def _paste_logo(self, logo: Image.Image, layer_name: str, box: dict) -> list[str]:
        """Fit and paste the logo into the calibrated box."""
        target_w = int(box.get("width", 200))
        target_h = int(box.get("height", 200))
        x = int(box.get("x", 0))
        y = int(box.get("y", 0))

        # Fit logo preserving aspect ratio
        ratio = min(target_w / logo.width, target_h / logo.height)
        new_w = max(1, round(logo.width * ratio))
        new_h = max(1, round(logo.height * ratio))
        resized = logo.resize((new_w, new_h), Image.LANCZOS)

        # Center within the box
        paste_x = x + (target_w - new_w) // 2
        paste_y = y + (target_h - new_h) // 2

        self.canvas.paste(resized, (paste_x, paste_y), resized)
        suffix = "" if layer_name == "LOGO_CLIENTE" else f" ({layer_name})"
        return [f"Logo colada em '{layer_name}'"]

    def _resolve_logo(self, logo_path: str) -> Path | None:
        """Resolve logo path, rejecting anything outside allowed upload directories."""
        try:
            resolved = Path(logo_path).resolve()
        except OSError:
            return None
        for root in ALLOWED_LOGO_ROOTS:
            if resolved.is_relative_to(root.resolve()):
                return resolved
        return None


def find_flat_image(template: dict, tema: TemaFundo | None = None) -> Path | None:
    """Find the flat artwork image for a template, optionally filtered by background theme.

    Flat images are stored alongside the PSD:
      gabaritos/my_template_flat_kraft.png
      gabaritos/my_template_flat_premium.png
      gabaritos/my_template_flat.png  (single background / fallback)

    Returns None if no flat image is found — caller should fall back to the PSD engine.
    """
    filename = template.get("filename", "")
    stem = Path(filename).stem
    parent = Path(filename).parent if Path(filename).parent != Path(filename) else settings.templates_dir
    # parent might be relative — resolve against templates_dir
    if not parent.is_absolute():
        parent = settings.templates_dir

    candidates: list[Path] = []
    if tema == TemaFundo.premium:
        candidates.append(parent / f"{stem}_flat_premium.png")
        candidates.append(parent / f"{stem}_flat_premium.jpg")
    elif tema == TemaFundo.tradicional:
        candidates.append(parent / f"{stem}_flat_kraft.png")
        candidates.append(parent / f"{stem}_flat_kraft.jpg")

    # Always check the generic flat image as fallback
    candidates.append(parent / f"{stem}_flat.png")
    candidates.append(parent / f"{stem}_flat.jpg")

    for path in candidates:
        if path.exists():
            return path
    return None
