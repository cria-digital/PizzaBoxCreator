"""Create a visual preflight by overlaying the die-cut PDF over artwork.

Uso:
    python scripts/preflight_die_overlay.py arte.jpg faca.pdf spec.json --output tmp/preflight.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.preflight import build_preflight_overlay


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sobrepoe a faca no canvas da arte para conferencia visual.")
    parser.add_argument("art", type=Path, help="Imagem da arte")
    parser.add_argument("die_pdf", type=Path, help="PDF da faca")
    parser.add_argument("spec", type=Path, help="JSON gerado por create_die_spec.py")
    parser.add_argument("--output", type=Path, required=True, help="Imagem de saida")
    parser.add_argument("--max-width", type=int, default=2400, help="Largura maxima do preview")
    parser.add_argument(
        "--fit",
        choices=["cover", "contain", "stretch"],
        default="cover",
        help="Como encaixar a arte no canvas da faca",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out = build_preflight_overlay(
        art_path=args.art,
        die_pdf_path=args.die_pdf,
        spec_path=args.spec,
        output_path=args.output,
        max_width=args.max_width,
        fit_mode=args.fit,
    )
    print(f"Preflight salvo: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

