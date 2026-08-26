"""Create a reusable die-cut spec JSON from a PDF.

Uso:
    python scripts/create_die_spec.py faca.pdf --name alcapizza_35 --output gabaritos/facas/alcapizza_35.spec.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.die_spec import build_die_spec, write_die_spec


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera JSON tecnico de faca a partir do TrimBox/BleedBox.")
    parser.add_argument("pdf", type=Path, help="PDF da faca")
    parser.add_argument("--name", required=True, help="Nome estavel da faca, ex: alcapizza_35")
    parser.add_argument("--product-type", default="pizza_box", help="Tipo de produto")
    parser.add_argument("--page", type=int, default=1, help="Pagina 1-based")
    parser.add_argument("--dpi", type=int, default=300, help="DPI alvo da arte final")
    parser.add_argument("--output", type=Path, required=True, help="Arquivo JSON de saida")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    spec = build_die_spec(
        args.pdf,
        name=args.name,
        product_type=args.product_type,
        page_number=args.page,
        dpi=args.dpi,
    )
    write_die_spec(spec, args.output)
    canvas = spec["canvas_px"]
    bleed = spec["bleed_size_mm"]
    print(f"Die spec salvo: {args.output}")
    print(f"Canvas: {bleed['width']} x {bleed['height']} mm | {canvas['width']} x {canvas['height']} px")
    print(f"Linha de corte: {spec['cutline_source']} | Arte final: {spec['canvas_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
