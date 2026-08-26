"""Color conversion helpers for print masters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageCms


DEFAULT_CMYK_PROFILE = Path(__file__).resolve().parents[1] / "psd" / "profiles" / "uswebcoatedswop.icc"


def build_rgb_to_cmyk_transform(icc_profile: Path = DEFAULT_CMYK_PROFILE) -> ImageCms.ImageCmsTransform:
    srgb = ImageCms.createProfile("sRGB")
    cmyk = ImageCms.getOpenProfile(str(icc_profile))
    return ImageCms.buildTransform(
        srgb,
        cmyk,
        "RGB",
        "CMYK",
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
    )


def build_cmyk_to_rgb_transform(icc_profile: Path = DEFAULT_CMYK_PROFILE) -> ImageCms.ImageCmsTransform:
    srgb = ImageCms.createProfile("sRGB")
    cmyk = ImageCms.getOpenProfile(str(icc_profile))
    return ImageCms.buildTransform(
        cmyk,
        srgb,
        "CMYK",
        "RGB",
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
    )


def profile_name(icc_profile: Path = DEFAULT_CMYK_PROFILE) -> str:
    if not icc_profile.exists():
        return ""
    return ImageCms.getProfileName(ImageCms.getOpenProfile(str(icc_profile))).strip()


def convert_rgb_to_cmyk(image: Image.Image, icc_profile: Path = DEFAULT_CMYK_PROFILE) -> Image.Image:
    if not icc_profile.exists():
        raise FileNotFoundError(f"Perfil ICC nao encontrado: {icc_profile}")
    return ImageCms.applyTransform(image.convert("RGB"), build_rgb_to_cmyk_transform(icc_profile))


def _tac_array(chunk: np.ndarray) -> np.ndarray:
    return chunk.astype(np.uint16).sum(axis=2) * (100.0 / 255.0)


def tac_stats(image: Image.Image, *, chunk_rows: int = 512) -> dict[str, Any]:
    if image.mode != "CMYK":
        raise ValueError("tac_stats exige imagem CMYK.")

    width, height = image.size
    max_tac = 0.0
    total_pixels = width * height
    over_260 = 0
    over_280 = 0
    over_300 = 0

    for top in range(0, height, chunk_rows):
        bottom = min(height, top + chunk_rows)
        chunk = np.asarray(image.crop((0, top, width, bottom)), dtype=np.uint8)
        tac = _tac_array(chunk)
        max_tac = max(max_tac, float(tac.max(initial=0)))
        over_260 += int((tac > 260).sum())
        over_280 += int((tac > 280).sum())
        over_300 += int((tac > 300).sum())

    return {
        "max_tac": round(max_tac, 2),
        "pixels": total_pixels,
        "over_260_pct": round(over_260 * 100.0 / total_pixels, 4) if total_pixels else 0.0,
        "over_280_pct": round(over_280 * 100.0 / total_pixels, 4) if total_pixels else 0.0,
        "over_300_pct": round(over_300 * 100.0 / total_pixels, 4) if total_pixels else 0.0,
    }


def limit_tac(image: Image.Image, tac_max: int = 300, *, chunk_rows: int = 256) -> Image.Image:
    """Clamp total area coverage by scaling CMY and preserving K."""
    if image.mode != "CMYK":
        raise ValueError("limit_tac exige imagem CMYK.")
    if tac_max <= 0 or tac_max > 400:
        raise ValueError("tac_max deve ficar entre 1 e 400.")

    width, height = image.size
    out = Image.new("CMYK", image.size)
    max_sum = tac_max * 255.0 / 100.0

    for top in range(0, height, chunk_rows):
        bottom = min(height, top + chunk_rows)
        arr = np.asarray(image.crop((0, top, width, bottom)), dtype=np.uint8).copy()
        cmy = arr[:, :, :3].astype(np.float32)
        k = arr[:, :, 3].astype(np.float32)
        cmy_sum = cmy.sum(axis=2)
        allowed = np.maximum(max_sum - k, 0.0)
        needs = cmy_sum > allowed
        scale = np.ones_like(cmy_sum, dtype=np.float32)
        np.divide(allowed, cmy_sum, out=scale, where=cmy_sum > 0)
        cmy[needs] *= scale[needs, None]
        arr[:, :, :3] = np.clip(np.rint(cmy), 0, 255).astype(np.uint8)
        out.paste(Image.fromarray(arr, "CMYK"), (0, top))

    return out


def convert_master_to_cmyk(
    *,
    master_path: Path,
    output_path: Path,
    icc_profile: Path = DEFAULT_CMYK_PROFILE,
    dpi: int = 300,
    tac_max: int | None = 300,
    proof_path: Path | None = None,
) -> dict[str, Any]:
    rgb = Image.open(master_path).convert("RGB")
    cmyk = convert_rgb_to_cmyk(rgb, icc_profile)
    before = tac_stats(cmyk)

    limited = False
    if tac_max is not None and before["max_tac"] > tac_max:
        cmyk = limit_tac(cmyk, tac_max=tac_max)
        limited = True
    after = tac_stats(cmyk)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    icc_bytes = icc_profile.read_bytes()
    cmyk.save(output_path, "TIFF", compression="tiff_lzw", dpi=(dpi, dpi), icc_profile=icc_bytes)

    result = {
        "source": str(master_path),
        "cmyk_master": str(output_path),
        "icc_profile": str(icc_profile),
        "icc_profile_name": profile_name(icc_profile),
        "dpi": dpi,
        "size_px": {"width": cmyk.width, "height": cmyk.height},
        "mode": cmyk.mode,
        "tac_max": tac_max,
        "tac_limited": limited,
        "tac_before": before,
        "tac_after": after,
    }

    if proof_path:
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof = ImageCms.applyTransform(cmyk, build_cmyk_to_rgb_transform(icc_profile))
        proof.save(proof_path, "JPEG", quality=90)
        result["rgb_proof"] = str(proof_path)

    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["metadata"] = str(metadata_path)
    return result

