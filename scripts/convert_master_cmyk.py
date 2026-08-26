"""Convert a RGB artwork master to a CMYK TIFF with ICC profile and TAC report.

Uso:
    python scripts/convert_master_cmyk.py master.png --output storage/art_masters/job_cmyk.tif
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.color import DEFAULT_CMYK_PROFILE, convert_master_to_cmyk


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Converte master RGB para CMYK com perfil ICC.")
    parser.add_argument("master", type=Path, help="Master RGB aprovado")
    parser.add_argument("--output", type=Path, required=True, help="TIFF CMYK de saida")
    parser.add_argument("--icc-profile", type=Path, default=DEFAULT_CMYK_PROFILE)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--tac-max", type=int, default=300, help="Limite de cobertura total de tinta")
    parser.add_argument("--no-tac-limit", action="store_true", help="Nao aplica limitador de TAC")
    parser.add_argument("--proof", type=Path, help="JPG RGB de prova visual apos conversao CMYK")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = convert_master_to_cmyk(
        master_path=args.master,
        output_path=args.output,
        icc_profile=args.icc_profile,
        dpi=args.dpi,
        tac_max=None if args.no_tac_limit else args.tac_max,
        proof_path=args.proof,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

