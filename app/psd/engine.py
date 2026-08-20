"""Core PSD editing engine using PhotoshopAPI."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageCms, ImageDraw

from app.config import settings
from app.models.commands import EditCommand, TemaFundo
from app.psd.calibration import layers_for_base
from app.psd.text_metrics import font_available, get_font, wrap_text

logger = logging.getLogger(__name__)

DEFAULT_CMYK_PROFILE = Path(__file__).parent / "profiles" / "uswebcoatedswop.icc"

ALLOWED_LOGO_ROOTS = (settings.temp_dir, settings.logos_dir)

# So estes tipos sobrevivem a composicao do preview e a conversao CMYK. Qualquer outro
# (SmartObjectLayer, camadas de ajuste/shape lidas como Layer base) e DESCARTADO.
SUPPORTED_LAYER_HINTS = ("GroupLayer", "ImageLayer", "TextLayer")


def _is_supported_layer(layer) -> bool:
    tname = type(layer).__name__
    return any(hint in tname for hint in SUPPORTED_LAYER_HINTS)


def rgb_channels(data: dict):
    """Return (red, green, blue) arrays from a PhotoshopAPI channel dict.

    get_image_data() keys channels by ChannelID (red=0, green=1, blue=2) but does NOT
    guarantee iteration order — some PSDs return them as [0, 2, 1]. Selecting positionally
    via list(data.values()) therefore swaps green/blue and corrupts colors in both the preview
    and the CMYK export. Index by channel id explicitly instead. Returns None if not RGB.
    """
    by_id: dict[int, object] = {}
    for key, arr in data.items():
        kid = key.value if hasattr(key, "value") else int(key)
        by_id[kid] = arr
    if not all(i in by_id for i in (0, 1, 2)):
        return None
    return by_id[0], by_id[1], by_id[2]


def text_fill_rgb(layer) -> tuple[int, int, int]:
    """RGB (0-255) of a text layer's fill color, matching how the preview renders it.

    PhotoshopAPI returns /FillColor /Values as 4 floats; empirically the usable RGB sits at
    [.., g, b, r]. Using one helper for both the preview and the CMYK export keeps the printed
    text color consistent with the preview the client approved. Falls back to black.
    """
    try:
        fc = layer.style_run_fill_color(0)
        if fc and len(fc) >= 4:
            _a, g, b, r = fc[0], fc[1], fc[2], fc[3]
            return (int(r * 255), int(g * 255), int(b * 255))
    except Exception:
        pass
    return (0, 0, 0)


def _rgb_to_cmyk_color(r: int, g: int, b: int, transform) -> list[float]:
    """Convert a single RGB color (0-255) to CMYK /Values (0-1), via ICC when available."""
    if transform is not None:
        try:
            px = ImageCms.applyTransform(Image.new("RGB", (1, 1), (r, g, b)), transform).getpixel((0, 0))
            return [v / 255.0 for v in px]
        except Exception:
            pass
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    k = 1.0 - max(rf, gf, bf)
    if k >= 1.0:
        return [0.0, 0.0, 0.0, 1.0]
    return [(1 - rf - k) / (1 - k), (1 - gf - k) / (1 - k), (1 - bf - k) / (1 - k), k]


def psd_read(path: str):
    """Read a PSD via PhotoshopAPI, retrying transient native failures.

    The native reader/writer occasionally fails intermittently under load (large files,
    rapid successive I/O on Windows). A couple of retries make the preview/CMYK pipeline
    reliable for production-sized PSDs instead of failing the whole order.
    """
    return _retry_native(lambda: psapi.LayeredFile.read(path), what=f"ler PSD {path}")


def psd_write(layered_file, path: str) -> None:
    _retry_native(lambda: layered_file.write(path), what=f"gravar PSD {path}")


def _retry_native(fn, what: str, attempts: int = 3, backoff: float = 0.2):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # native lib raises a range of error types
            last_exc = exc
            if attempt < attempts:
                logger.warning("Falha ao %s (tentativa %d/%d): %s — retry",
                               what, attempt, attempts, exc)
                time.sleep(backoff * attempt)
    raise last_exc


def _resolve_logo_path(logo_path: str) -> Path | None:
    """Resolve a logo path, rejecting anything outside the allowed upload directories.

    logo_path comes straight from client-supplied JSON (EditCommand/ClientCreate), so
    without this check a caller could point it at any file readable by the server
    (e.g. logo_path="C:/Windows/...") and have its contents baked into their PSD/preview.
    """
    try:
        resolved = Path(logo_path).resolve()
    except OSError:
        return None

    for root in ALLOWED_LOGO_ROOTS:
        if resolved.is_relative_to(root.resolve()):
            return resolved
    return None


def _fit_logo_to_layer(img: Image.Image, target_w: int, target_h: int) -> tuple[Image.Image, np.ndarray]:
    """Scale the logo to fit inside the layer's box without distorting it, centered,
    and return an RGB frame plus the mask needed to keep transparent padding/background
    invisible (ImageLayer.set_image_data has no RGB-mode alpha channel, only a pixel mask).
    """
    ratio = min(target_w / img.width, target_h / img.height)
    new_w = max(1, round(img.width * ratio))
    new_h = max(1, round(img.height * ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(resized, (x, y), resized)

    rgb = canvas.convert("RGB")
    mask = np.array(canvas.split()[-1], dtype=np.uint8)
    return rgb, mask


def _check_text_overflow(layer, text: str) -> str | None:
    """Warn (don't block) when the new text likely won't fit the layer's text box."""
    try:
        if not layer.is_box_text:
            return None
        box_width = layer.box_width()
        box_height = layer.box_height()
        font_size = layer.style_run_font_size(0)
    except Exception:
        return None

    if box_width <= 0 or box_height <= 0:
        return None

    font_name = getattr(layer, "primary_font_name", None)
    font = get_font(max(int(font_size), 10), font_name)
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = wrap_text(draw, text, font, box_width)
    estimated_height = len(lines) * font_size * 1.2

    if estimated_height > box_height * 1.15:
        return (f"AVISO: texto de '{layer.name}' pode nao caber na area reservada "
                f"({len(lines)} linha(s) estimada(s))")
    return None


class PsdEngine:
    """Opens a template PSD, applies edit commands, and writes the result."""

    def __init__(self, template_path: Path):
        self.template_path = template_path
        self.file: psapi.LayeredFile_8bit = psd_read(str(template_path))
        self._layer_cache: dict[str, psapi.Layer_8bit] = {}
        self._build_cache()

    def _build_cache(self):
        for layer in self.file.flat_layers:
            if layer.name in self._layer_cache:
                logger.warning(
                    "Nome de camada duplicado '%s' no PSD — primeira ocorrencia sera sobrescrita",
                    layer.name,
                )
            self._layer_cache[layer.name] = layer

    def find_layer(self, name: str):
        return self._layer_cache.get(name)

    def unsupported_layers(self) -> list[str]:
        """Warnings for layers that will be silently dropped from preview and CMYK.

        Smart objects, shape/vector layers, adjustment layers and layer effects can't be
        composited without Photoshop, so they vanish from the production file. Surfacing them
        lets the operator flatten/rasterize the art before it goes to print instead of
        discovering the loss on the printed box.
        """
        warnings: list[str] = []
        for layer in self.file.flat_layers:
            if not _is_supported_layer(layer):
                warnings.append(
                    f"AVISO: camada '{layer.name}' ({type(layer).__name__}) nao e suportada e "
                    f"sera DESCARTADA no arquivo de producao — achate/rasterize no Photoshop antes"
                )
        return warnings

    def font_warnings(self) -> list[str]:
        """Warn when a text layer's font isn't installed on the server.

        The preview would then fall back to Arial while the CMYK export keeps the real font
        name — so the client approves a typeface different from what actually prints. Install
        the font on the server to make the preview match production.
        """
        warnings: list[str] = []
        seen: set[str] = set()
        for layer in self.file.flat_layers:
            if "TextLayer" not in type(layer).__name__:
                continue
            font_name = getattr(layer, "primary_font_name", None)
            if font_name and font_name not in seen and not font_available(font_name):
                seen.add(font_name)
                warnings.append(
                    f"AVISO: fonte '{font_name}' nao esta instalada no servidor — o preview usa "
                    f"Arial, mas a producao mantem '{font_name}'. Instale a fonte para o preview "
                    f"bater com a impressao."
                )
        return warnings

    def _layers_for(self, base: str) -> list:
        """All layers belonging to a field/element base, across box faces (BASE, BASE_2, ...)."""
        return [self.find_layer(n) for n in layers_for_base(self._layer_cache.keys(), base)]

    def apply(self, cmd: EditCommand, calibration: dict | None = None) -> list[str]:
        """Apply an EditCommand to the loaded PSD. Returns list of changes made.

        `calibration` is the template's per-layer geometry override (see
        app.psd.calibration): a dict mapping layer name -> {x, y, width, height, font_size}.
        When present, each edited layer is repositioned/resized to those values so the
        editable content lands on the artwork's reserved areas instead of the PSD's
        placeholder positions.
        """
        calibration = calibration or {}
        changes: list[str] = []

        if cmd.telefone is not None:
            changes += self._set_text("TEXTO_TELEFONE", cmd.telefone, calibration)

        if cmd.instagram is not None:
            changes += self._set_text("TEXTO_INSTAGRAM", cmd.instagram, calibration)

        if cmd.frase is not None:
            changes += self._set_text("TEXTO_FRASE_OPCIONAL", cmd.frase, calibration)

        if cmd.tema_fundo is not None:
            changes += self._set_background(cmd.tema_fundo)

        if cmd.adicionar_selo_entrega:
            changes += self._toggle_layer("selo_entrega_rapida", True)

        if cmd.adicionar_forno_lenha:
            changes += self._toggle_layer("ilustracao_forno_lenha", True)

        if cmd.logo_path:
            changes += self._replace_logo(cmd.logo_path, calibration)

        return changes

    def _set_text(self, base: str, text: str, calibration: dict | None = None) -> list[str]:
        """Set `text` on every layer of this field (one per box face: BASE, BASE_2, ...)."""
        calibration = calibration or {}
        names = layers_for_base(self._layer_cache.keys(), base)
        if not names:
            return [f"AVISO: Camada '{base}' nao encontrada"]

        changes: list[str] = []
        for layer_name in names:
            layer = self.find_layer(layer_name)
            if not isinstance(layer, psapi.TextLayer_8bit):
                changes.append(f"AVISO: '{layer_name}' nao e camada de texto")
                continue

            self._apply_text_geometry(layer, layer_name, calibration)
            layer.set_text(text)
            changes.append(f"Texto '{layer_name}' alterado para: {text}")

            overflow_warning = _check_text_overflow(layer, text)
            if overflow_warning:
                changes.append(overflow_warning)
        return changes

    def _apply_text_geometry(self, layer, layer_name: str, calibration: dict) -> None:
        """Reposition/resize a text layer per calibration. `y` is the box top, so the
        baseline (transform_ty) is y + font_size to match how the renderer draws it."""
        box = calibration.get(layer_name)
        if not isinstance(box, dict):
            return

        font_size = box.get("font_size")
        if font_size:
            try:
                layer.set_style_run_font_size(0, float(font_size))
            except Exception as exc:
                logger.warning("Nao foi possivel aplicar font_size em '%s': %s", layer_name, exc)
        else:
            try:
                font_size = float(layer.style_run_font_size(0))
            except Exception:
                font_size = 0.0

        if box.get("x") is not None:
            layer.set_transform_tx(float(box["x"]))
        if box.get("y") is not None:
            layer.set_transform_ty(float(box["y"]) + float(font_size or 0))

        width, height = box.get("width"), box.get("height")
        if width and height:
            try:
                layer.set_box_size(float(width), float(height))
            except Exception as exc:
                logger.warning("Nao foi possivel aplicar box_size em '%s': %s", layer_name, exc)

    def _set_background(self, tema: TemaFundo) -> list[str]:
        kraft = self._layers_for("fundo_kraft_tradicional")
        premium = self._layers_for("fundo_preto_premium")

        show, hide = (premium, kraft) if tema == TemaFundo.premium else (kraft, premium)
        for layer in show:
            layer.is_visible = True
        for layer in hide:
            layer.is_visible = False

        label = "premium (preto)" if tema == TemaFundo.premium else "tradicional (kraft)"
        return [f"Fundo alterado para: {label}"]

    def _toggle_layer(self, base: str, visible: bool) -> list[str]:
        """Toggle every face's copy of a decoration layer (BASE, BASE_2, ...)."""
        layers = self._layers_for(base)
        if not layers:
            return [f"AVISO: Camada '{base}' nao encontrada"]
        for layer in layers:
            layer.is_visible = visible
        state = "ativada" if visible else "desativada"
        return [f"Camada '{base}' {state}"]

    def _replace_logo(self, logo_path: str, calibration: dict | None = None) -> list[str]:
        """Place the logo on every logo layer (one per box face: LOGO_CLIENTE, LOGO_CLIENTE_2, ...)."""
        calibration = calibration or {}
        names = layers_for_base(self._layer_cache.keys(), "LOGO_CLIENTE")
        if not names:
            return ["AVISO: Camada 'LOGO_CLIENTE' nao encontrada"]

        path = _resolve_logo_path(logo_path)
        if path is None:
            return [f"AVISO: Caminho de logo nao permitido: {logo_path}"]
        if not path.exists():
            return [f"AVISO: Arquivo de logo nao encontrado: {logo_path}"]

        try:
            img = Image.open(path)
            img.load()
        except Exception:
            return [f"AVISO: Nao foi possivel ler o arquivo de logo (formato invalido?): {path.name}"]

        rgba = img.convert("RGBA")
        cid = psapi.enum.ChannelID
        changes: list[str] = []
        for layer_name in names:
            layer = self.find_layer(layer_name)
            if not isinstance(layer, psapi.ImageLayer_8bit):
                changes.append(f"AVISO: '{layer_name}' nao e camada de imagem")
                continue
            self._apply_logo_geometry(layer, layer_name, calibration)
            rgb, mask = _fit_logo_to_layer(rgba, layer.width, layer.height)
            arr = np.array(rgb, dtype=np.uint8)
            layer.set_image_data({
                cid.red: np.ascontiguousarray(arr[:, :, 0]),
                cid.green: np.ascontiguousarray(arr[:, :, 1]),
                cid.blue: np.ascontiguousarray(arr[:, :, 2]),
            })
            layer.mask = mask
            suffix = "" if layer_name == "LOGO_CLIENTE" else f" ({layer_name})"
            changes.append(f"Logo substituido com: {path.name}{suffix}")
        return changes

    def _apply_logo_geometry(self, layer, layer_name: str, calibration: dict) -> None:
        """Resize/move the logo layer per calibration. center_x/center_y are treated as
        the layer's top-left (matching the renderer's paste position)."""
        box = calibration.get(layer_name)
        if not isinstance(box, dict):
            return
        try:
            if box.get("width") and box.get("height"):
                layer.width = int(round(float(box["width"])))
                layer.height = int(round(float(box["height"])))
            if box.get("x") is not None:
                layer.center_x = float(box["x"])
            if box.get("y") is not None:
                layer.center_y = float(box["y"])
        except Exception as exc:
            logger.warning("Nao foi possivel aplicar geometria de logo em '%s': %s", layer_name, exc)

    def save(self, output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        psd_write(self.file, str(output_path))

    def save_as_cmyk(self, output_path: Path, source_psd: Path | None = None,
                     icc_profile: Path | None = None, dpi: float | None = None) -> list[str]:
        """Save a copy converting RGB layers to CMYK for print production.

        Args:
            output_path: Where to write the CMYK PSD.
            source_psd: PSD to convert (defaults to the edited output, not the original template).
            icc_profile: ICC profile used both to color-manage the RGB->CMYK conversion and to
                embed in the output. Defaults to the U.S. Web Coated (SWOP) v2 profile, the
                standard used by the print shop's real production files.
            dpi: Resolution stamped on the output. Defaults to settings.production_dpi (300);
                the source gabaritos are usually 72 DPI, which the print shop can't use as-is.

        Returns a list of warnings for layers that were dropped (unsupported types).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if icc_profile is None:
            icc_profile = DEFAULT_CMYK_PROFILE
        if dpi is None:
            dpi = settings.production_dpi

        source = psd_read(str(source_psd)) if source_psd else self.file

        cmyk_file = psapi.LayeredFile_8bit(
            psapi.enum.ColorMode.cmyk,
            source.width,
            source.height,
        )

        transform = _build_cmyk_transform(icc_profile) if icc_profile.exists() else None

        if icc_profile.exists():
            cmyk_file.icc = icc_profile

        dropped: list[str] = []
        _copy_layers_to_cmyk(source.layers, cmyk_file, target_group=None,
                             transform=transform, dropped=dropped)

        # Stamp print resolution so the gráfica opens the file at the right physical size
        # instead of the 72 DPI the gabaritos carry.
        try:
            cmyk_file.dpi = float(dpi)
        except Exception:
            logger.warning("Nao foi possivel gravar DPI %s no CMYK", dpi)

        psd_write(cmyk_file, str(output_path))
        return dropped


def _build_cmyk_transform(icc_profile: Path) -> ImageCms.ImageCmsTransform:
    """Build a color-managed sRGB->CMYK transform using a real destination profile.

    Replaces the naive r/g/b subtractive formula, which has no notion of how
    a specific press/paper combination renders color and is the source of the
    documented "desvio de cor" in CMYK exports.
    """
    srgb = ImageCms.createProfile("sRGB")
    cmyk = ImageCms.getOpenProfile(str(icc_profile))
    return ImageCms.buildTransform(
        srgb, cmyk, "RGB", "CMYK",
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
    )


def _copy_layers_to_cmyk(layers, cmyk_file, target_group, transform=None, dropped=None):
    if dropped is None:
        dropped = []
    for layer in layers:
        tname = type(layer).__name__

        if "GroupLayer" in tname:
            grp = psapi.GroupLayer_8bit(
                layer.name,
                is_visible=layer.is_visible,
                is_locked=layer.is_locked,
            )
            if target_group:
                target_group.add_layer(cmyk_file, grp)
            else:
                cmyk_file.add_layer(grp)
            if hasattr(layer, "layers"):
                _copy_layers_to_cmyk(layer.layers, cmyk_file, grp,
                                     transform=transform, dropped=dropped)

        elif "TextLayer" in tname:
            font_name = getattr(layer, "primary_font_name", None) or "ArialMT"
            txt = psapi.TextLayer_8bit(
                layer.name,
                layer.text,
                font=font_name,
                font_size=layer.style_run_font_size(0),
                position_x=layer.transform_tx,
                position_y=layer.transform_ty,
                color_mode=psapi.enum.ColorMode.cmyk,
                is_visible=layer.is_visible,
            )

            # Carry the text color across so production text matches the approved preview
            # (instead of defaulting to black, which is invisible on dark/premium art).
            cmyk_color = _rgb_to_cmyk_color(*text_fill_rgb(layer), transform)
            try:
                txt.set_style_normal_fill_color(cmyk_color)
                txt.set_style_run_fill_color(0, cmyk_color)
            except Exception:
                logger.warning("Nao foi possivel aplicar a cor CMYK ao texto '%s'", layer.name)

            # Preserve paragraph-box wrapping so long text breaks the same as in the preview.
            try:
                if layer.is_box_text:
                    bw, bh = layer.box_width(), layer.box_height()
                    if bw > 0 and bh > 0:
                        if txt.is_box_text:
                            txt.set_box_size(bw, bh)
                        else:
                            txt.convert_to_box_text(bw, bh)
            except Exception:
                logger.warning("Nao foi possivel preservar o box do texto '%s'", layer.name)

            if target_group:
                target_group.add_layer(cmyk_file, txt)
            else:
                cmyk_file.add_layer(txt)

        elif "ImageLayer" in tname:
            data = layer.get_image_data()
            if not data:
                continue

            rgb = rgb_channels(data)
            if rgb is not None:
                r, g, b = rgb
                if transform is not None:
                    c, m, y, k = _rgb_to_cmyk_icc(r, g, b, transform)
                else:
                    c, m, y, k = _rgb_to_cmyk(r, g, b)
            else:
                # Sort by channel id to guarantee C/M/Y/K order (0-3) regardless of dict
                # iteration order — same issue fixed in gabarito_builder for CMYK source PSDs.
                sorted_channels = sorted(data.items(), key=lambda kv: int(kv[0]))
                if len(sorted_channels) >= 4:
                    c, m, y, k = (sorted_channels[0][1], sorted_channels[1][1],
                                  sorted_channels[2][1], sorted_channels[3][1])
                else:
                    continue

            cmyk_data = {
                0: np.ascontiguousarray(c),
                1: np.ascontiguousarray(m),
                2: np.ascontiguousarray(y),
                3: np.ascontiguousarray(k),
            }
            # The rest of the codebase treats center_x/center_y as the layer's TOP-LEFT
            # (that's how the renderer pastes), but ImageLayer_8bit's pos_x/pos_y is the
            # true center. Converting here keeps full-canvas art from shifting half a
            # canvas off-screen in the production CMYK file.
            cmyk_layer = psapi.ImageLayer_8bit(
                cmyk_data, layer.name,
                width=layer.width, height=layer.height,
                pos_x=int(layer.center_x + layer.width / 2),
                pos_y=int(layer.center_y + layer.height / 2),
                opacity=layer.opacity,
                is_visible=layer.is_visible,
                is_locked=layer.is_locked,
                color_mode=psapi.enum.ColorMode.cmyk,
            )
            if layer.has_mask():
                cmyk_layer.mask = np.array(layer.mask, dtype=np.uint8)
            if target_group:
                target_group.add_layer(cmyk_file, cmyk_layer)
            else:
                cmyk_file.add_layer(cmyk_layer)

        else:
            # Smart objects, shape/vector and adjustment layers can't be composited without
            # Photoshop — they're dropped. Record them so the operator is warned instead of
            # the loss being silent.
            dropped.append(
                f"AVISO: camada '{layer.name}' ({tname}) DESCARTADA na conversao CMYK — "
                f"nao suportada; achate/rasterize no Photoshop antes de exportar"
            )
            logger.warning("Camada nao suportada descartada no CMYK: %s (%s)", layer.name, tname)


def _rgb_to_cmyk_icc(
    r: np.ndarray, g: np.ndarray, b: np.ndarray, transform: ImageCms.ImageCmsTransform
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Color-managed RGB->CMYK conversion through a real press profile (e.g. SWOP)."""
    rgb = np.dstack([r, g, b])
    img = Image.fromarray(rgb, mode="RGB")
    cmyk_img = ImageCms.applyTransform(img, transform)
    cmyk = np.array(cmyk_img)
    return (
        np.ascontiguousarray(cmyk[:, :, 0]),
        np.ascontiguousarray(cmyk[:, :, 1]),
        np.ascontiguousarray(cmyk[:, :, 2]),
        np.ascontiguousarray(cmyk[:, :, 3]),
    )


def _rgb_to_cmyk(
    r: np.ndarray, g: np.ndarray, b: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Naive RGB→CMYK conversion (no ICC profile). Fallback when no profile is available."""
    rf = r.astype(np.float32) / 255.0
    gf = g.astype(np.float32) / 255.0
    bf = b.astype(np.float32) / 255.0

    k = 1.0 - np.maximum(np.maximum(rf, gf), bf)
    denom = np.where(k < 1.0, 1.0 - k, 1.0)

    c = ((1.0 - rf - k) / denom * 255).clip(0, 255).astype(np.uint8)
    m = ((1.0 - gf - k) / denom * 255).clip(0, 255).astype(np.uint8)
    y = ((1.0 - bf - k) / denom * 255).clip(0, 255).astype(np.uint8)
    k_out = (k * 255).clip(0, 255).astype(np.uint8)

    return c, m, y, k_out
