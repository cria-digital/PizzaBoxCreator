"""CLI wrapper to inspect PDF page boxes used to derive print geometry.

Uso:
    python scripts/inspect_pdf_boxes.py arquivo.pdf --dpi 300
    python scripts/inspect_pdf_boxes.py arquivo.pdf --page 1 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.pdf_boxes import format_human, inspect_pdf


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspeciona MediaBox, TrimBox e BleedBox de um PDF.")
    parser.add_argument("pdf", type=Path, help="Caminho do PDF")
    parser.add_argument("--page", type=int, default=1, help="Pagina 1-based")
    parser.add_argument("--dpi", type=int, default=300, help="DPI usado para converter pontos em pixels")
    parser.add_argument("--json", action="store_true", help="Imprime saida em JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = inspect_pdf(args.pdf, page_number=args.page, dpi=args.dpi)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_human(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
