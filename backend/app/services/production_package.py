"""Production package delivery: bundles all assets a designer needs after client approval.

When the client approves a preview, the designer needs:
1. The approved preview image (what the client saw and signed off on).
2. The client logo (processed, background removed if possible).
3. The exact text content and their calibrated positions on the artwork.
4. The flat artwork image(s) — the original design that was never modified by the system.

Everything is zipped into a single file the designer can download and open in Photoshop
to apply the final touches with the real fonts, effects and layers.
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def build_production_package(
    order: dict,
    template: dict,
    preview_path: str | None,
    output_dir: Path | None = None,
) -> Path | None:
    """Create a zip package with all production assets for the designer.

    Returns the zip path, or None if there isn't enough data to build a package.
    """
    if not preview_path or not Path(preview_path).exists():
        logger.warning("Pedido %s: preview nao encontrado, pacote nao gerado", order.get("id"))
        return None

    if output_dir is None:
        output_dir = settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    order_id = order["id"]
    zip_path = output_dir / f"pedido_{order_id}_producao.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Approved preview
        zf.write(preview_path, f"pedido_{order_id}_aprovado.jpg")

        # 2. Client logo (if uploaded)
        edit_data = order.get("edit_data", {})
        logo_path = edit_data.get("logo_path")
        if logo_path and Path(logo_path).exists():
            zf.write(logo_path, f"logo_cliente{Path(logo_path).suffix}")

        # 3. Flat artwork image(s) — the original design
        _add_flat_artworks(zf, template, order_id)

        # 4. Specification JSON — texts, positions, metadata
        spec = _build_spec(order, template)
        zf.writestr(f"pedido_{order_id}_spec.json", json.dumps(spec, indent=2, ensure_ascii=False))

        # 5. Readme for the designer
        readme = _build_readme(order, template)
        zf.writestr("LEIA_ME.txt", readme)

    logger.info("Pacote de producao gerado: %s", zip_path)
    return zip_path


def _add_flat_artworks(zf: zipfile.ZipFile, template: dict, order_id: int) -> None:
    """Add flat artwork images to the package if available."""
    filename = template.get("filename", "")
    stem = Path(filename).stem
    parent = settings.templates_dir

    patterns = [
        f"{stem}_flat.png", f"{stem}_flat.jpg",
        f"{stem}_flat_kraft.png", f"{stem}_flat_kraft.jpg",
        f"{stem}_flat_premium.png", f"{stem}_flat_premium.jpg",
    ]
    for pattern in patterns:
        path = parent / pattern
        if path.exists():
            zf.write(path, f"arte/{path.name}")


def _build_spec(order: dict, template: dict) -> dict:
    """Build a JSON specification the designer can use to apply the exact content."""
    edit_data = order.get("edit_data", {})
    calibration = template.get("calibration", {})

    return {
        "pedido_id": order["id"],
        "cliente": {
            "nome": order.get("client_name", ""),
            "telefone": edit_data.get("telefone", ""),
            "instagram": edit_data.get("instagram", ""),
        },
        "modelo": {
            "nome": template.get("display_name", ""),
            "tipo": template.get("product_type", "pizza"),
            "tamanho_cm": template.get("size_cm"),
        },
        "textos": {
            "telefone": edit_data.get("telefone", ""),
            "instagram": edit_data.get("instagram", ""),
            "frase": edit_data.get("frase", ""),
        },
        "tema_fundo": edit_data.get("tema_fundo", "tradicional"),
        "calibracao": calibration,
        "observacoes": "Aplique os textos e logo nas posicoes indicadas pela calibracao. "
                       "A imagem aprovada (preview) mostra o resultado esperado.",
    }


def _build_readme(order: dict, template: dict) -> str:
    """Generate a readme file for the designer."""
    return (
        f"PACOTE DE PRODUCAO — Pedido #{order['id']}\n"
        f"{'=' * 50}\n\n"
        f"Este pacote contem todos os assets necessarios para fechar a arte para impressao.\n\n"
        f"CONTEUDO:\n"
        f"  - pedido_{order['id']}_aprovado.jpg  : Preview aprovado pelo cliente\n"
        f"  - logo_cliente.*                     : Logo do cliente (fundo removido)\n"
        f"  - arte/                              : Imagem(is) plana(s) da arte original\n"
        f"  - pedido_{order['id']}_spec.json     : Posicoes exatas de texto e logo\n"
        f"  - LEIA_ME.txt                        : Este arquivo\n\n"
        f"COMO USAR:\n"
        f"  1. Abra a arte original no Photoshop\n"
        f"  2. Consulte o arquivo spec.json para as posicoes exatas de cada elemento\n"
        f"  3. Aplique os textos com as fontes e efeitos do design original\n"
        f"  4. Posicione a logo conforme o spec\n"
        f"  5. Exporte CMYK para a grafica\n\n"
        f"O preview aprovado serve como referencia visual — e exatamente o que o cliente esperava.\n"
    )


def get_package_path(order_id: int) -> Path | None:
    """Check if a production package exists for an order."""
    path = settings.output_dir / f"pedido_{order_id}_producao.zip"
    return path if path.exists() else None
