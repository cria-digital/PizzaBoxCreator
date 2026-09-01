"""CLI: bridge a flattened factory PSD (CMYK/RGB, no named layers) into an editable gabarito.

Thin wrapper around app.psd.gabarito_builder (shared with the catalog upload flow).

Uso: python scripts/build_gabarito_from_flat.py "<arquivo.psd>" [saida.psd]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.psd.gabarito_builder import build_editable_gabarito


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("gabaritos") / f"{src.stem}_editavel.psd"
    calibration = build_editable_gabarito(src, out)
    out.with_suffix(".calibration.json").write_text(
        json.dumps(calibration, indent=2), encoding="utf-8")
    print(f"Gabarito editavel criado: {out}")
    print(f"Calibracao: {out.with_suffix('.calibration.json')}")


if __name__ == "__main__":
    main()
