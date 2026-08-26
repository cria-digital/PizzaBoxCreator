"""Create a full-size artwork master from a source image and die spec.

Uso:
    python scripts/create_art_master.py arte.png spec.json --output storage/art_masters/job_1_master.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.print_specs.art_master import build_art_master


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera master de arte no canvas tecnico do BleedBox.")
    parser.add_argument("source", type=Path, help="Imagem fonte, normalmente saida da IA")
    parser.add_argument("spec", type=Path, help="Die spec JSON")
    parser.add_argument("--output", type=Path, required=True, help="PNG master em tamanho final")
    parser.add_argument("--preview", type=Path, help="Preview reduzido")
    parser.add_argument("--preview-max-width", type=int, default=2400)
    parser.add_argument("--watermark", default="")
    parser.add_argument(
        "--fit",
        choices=["cover", "contain", "stretch"],
        default="cover",
        help="Como encaixar a imagem fonte no canvas final",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = build_art_master(
        source_path=args.source,
        spec_path=args.spec,
        output_path=args.output,
        fit_mode=args.fit,
        preview_path=args.preview,
        preview_max_width=args.preview_max_width,
        watermark=args.watermark,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
