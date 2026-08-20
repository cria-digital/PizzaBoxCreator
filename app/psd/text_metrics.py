"""Font loading and text-wrapping shared by the preview renderer and the overflow check
in the PSD engine, so both estimate line breaks the same way."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

FALLBACK_FONTS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _resolve_font_path(font_name: str | None) -> Path | None:
    """Best-effort match of a PSD font name (e.g. 'ArialMT') to an installed font file.

    Windows keeps a registry map of friendly font names to filenames under
    HKLM\\...\\Fonts; a PSD's font name rarely matches the filename directly
    (`ArialMT` vs `arial.ttf`), so this is the only reliable way to find it.
    Without this, the preview always renders in Arial regardless of the
    template's real font, while the CMYK export (engine._copy_layers_to_cmyk)
    already carries the real font name through — so what the client approves
    can look different from what actually prints.
    """
    if not font_name:
        return None

    if sys.platform == "win32":
        try:
            import winreg
            normalized = font_name.replace("-", "").replace(" ", "").lower()
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
            ) as key:
                i = 0
                while True:
                    try:
                        reg_name, filename, _ = winreg.EnumValue(key, i)
                    except OSError:
                        break
                    i += 1
                    candidate = reg_name.split(" (")[0].replace("-", "").replace(" ", "").lower()
                    if candidate == normalized or normalized in candidate or candidate in normalized:
                        path = Path(filename)
                        if not path.is_absolute():
                            path = Path("C:/Windows/Fonts") / filename
                        if path.exists():
                            return path
        except OSError:
            pass
        return None

    # Linux/macOS: try fc-match to resolve the font name via fontconfig
    try:
        import subprocess
        result = subprocess.run(
            ["fc-match", "--format=%{file}", font_name],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            path = Path(result.stdout.strip())
            if path.exists():
                return path
    except Exception:
        pass
    return None


def font_available(font_name: str | None) -> bool:
    """True if the PSD's named font resolves to an installed file, so the preview renders it
    instead of silently falling back to Arial (which would misrepresent the printed typeface)."""
    return _resolve_font_path(font_name) is not None


def get_font(size: int, font_name: str | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    resolved = _resolve_font_path(font_name)
    if resolved:
        try:
            return ImageFont.truetype(str(resolved), size)
        except OSError:
            pass

    for path in FALLBACK_FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> list[str]:
    """Greedy word-wrap so text fits within max_width when drawn with font."""
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
