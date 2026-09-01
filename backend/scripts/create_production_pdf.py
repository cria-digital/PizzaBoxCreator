"""Create a print-sized artwork PDF from an approved master image.

Uso:
    python scripts/create_production_pdf.py master.png spec.json --output output/pdf/arte.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.production_pdf import build_artwork_pdf, build_cmyk_artwork_pdf, write_pdf_metadata


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera PDF de arte no tamanho do BleedBox.")
    parser.add_argument("master", type=Path, help="Master de arte no canvas tecnico")
    parser.add_argument("spec", type=Path, help="Die spec JSON")
    parser.add_argument("--output", type=Path, required=True, help="PDF de arte de saida")
    parser.add_argument("--quality", type=int, default=95, help="Qualidade da imagem embutida")
    parser.add_argument("--cmyk", action="store_true", help="Entrada e PDF de saida em CMYK")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.cmyk:
        result = build_cmyk_artwork_pdf(
            cmyk_path=args.master,
            spec_path=args.spec,
            output_path=args.output,
            quality=args.quality,
        )
    else:
        result = build_artwork_pdf(
            master_path=args.master,
            spec_path=args.spec,
            output_path=args.output,
            quality=args.quality,
        )
    metadata = write_pdf_metadata(result, args.output)
    result["metadata"] = str(metadata)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
