from __future__ import annotations

from PIL import Image

from app.print_specs.color import (
    DEFAULT_CMYK_PROFILE,
    convert_master_to_cmyk,
    convert_rgb_to_cmyk,
    limit_tac,
    profile_name,
    tac_stats,
)


def test_convert_rgb_to_cmyk_uses_icc_profile():
    img = Image.new("RGB", (4, 4), (255, 0, 0))

    converted = convert_rgb_to_cmyk(img, DEFAULT_CMYK_PROFILE)

    assert converted.mode == "CMYK"
    assert converted.size == (4, 4)
    assert profile_name(DEFAULT_CMYK_PROFILE)


def test_limit_tac_scales_cmy_and_preserves_k():
    img = Image.new("CMYK", (1, 1), (255, 255, 255, 128))

    limited = limit_tac(img, tac_max=300)
    c, m, y, k = limited.getpixel((0, 0))

    assert k == 128
    assert c + m + y + k <= 765


def test_tac_stats_reports_thresholds():
    img = Image.new("CMYK", (2, 1))
    img.putpixel((0, 0), (255, 255, 255, 0))
    img.putpixel((1, 0), (0, 0, 0, 255))

    stats = tac_stats(img)

    assert stats["max_tac"] == 300.0
    assert stats["over_280_pct"] == 50.0
    assert stats["over_300_pct"] == 0.0


def test_convert_master_to_cmyk_writes_tiff_metadata_and_proof(tmp_path):
    master = tmp_path / "master.png"
    output = tmp_path / "master_cmyk.tif"
    proof = tmp_path / "proof.jpg"
    Image.new("RGB", (8, 4), (10, 20, 30)).save(master)

    result = convert_master_to_cmyk(
        master_path=master,
        output_path=output,
        proof_path=proof,
        tac_max=300,
    )

    assert output.exists()
    assert output.with_suffix(".json").exists()
    assert proof.exists()
    assert Image.open(output).mode == "CMYK"
    assert result["mode"] == "CMYK"
    assert result["size_px"] == {"width": 8, "height": 4}

