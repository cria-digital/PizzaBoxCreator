"""Run the paid Gemini image generation pilot through the print pipeline.

Uso:
    python scripts/run_ai_art_pilot.py --job-id alcapizza_ai_001 --brand "Pizzaria Demo" \
      --spec gabaritos/facas/alcapizza_35.spec.json --die-pdf "/path/faca.pdf"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.ai_art_pipeline import run_ai_art_pipeline


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera arte por IA e roda master/CMYK/PDF.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--die-pdf", type=Path, required=True)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--product-type", default="pizza")
    parser.add_argument("--phone", default="")
    parser.add_argument("--instagram", default="")
    parser.add_argument("--frase", default="Sua pizza chegou!")
    parser.add_argument("--tema", default="premium", choices=["premium", "tradicional"])
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    parser.add_argument("--tac-max", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = run_ai_art_pipeline(
        job_id=args.job_id,
        spec_path=args.spec,
        die_pdf_path=args.die_pdf,
        client={"name": args.brand, "phone": args.phone, "instagram": args.instagram},
        template={"product_type": args.product_type},
        edit_data={
            "telefone": args.phone,
            "instagram": args.instagram,
            "frase": args.frase,
            "tema_fundo": args.tema,
        },
        reference_paths=args.reference,
        fit_mode=args.fit,
        tac_max=args.tac_max,
    )
    printable = {k: v for k, v in result.items() if k != "prompt"}
    print(json.dumps(printable, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
