"""Seed the templates table from PSD files in gabaritos/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.db.session import init_db, get_db
from app.db import repositories as repo
from app.psd.fields import build_editable_fields
from app.psd.renderer import generate_preview


def derive_template_info(filename: str) -> dict:
    """Extract display name, size, and product type from filename."""
    name = Path(filename).stem
    lower = name.lower()

    size = None
    for s in [25, 30, 35, 40, 45, 50]:
        if str(s) in name:
            size = s
            break

    if "hambur" in lower:
        product_type = "hamburger"
    elif "sacola" in lower:
        product_type = "sacola"
    else:
        product_type = "pizza"

    display = name.replace("_", " ").replace("-", " ").strip()
    if "teste" in lower:
        display = f"Caixa Pizza {size or '?'}cm - Modelo Teste"

    return {"display_name": display, "size_cm": size, "product_type": product_type}


def main():
    settings.ensure_dirs()
    init_db()
    db = next(get_db())

    psd_files = list(settings.templates_dir.glob("*.psd"))
    if not psd_files:
        print("Nenhum PSD encontrado em", settings.templates_dir)
        return

    for psd_path in psd_files:
        existing = repo.template_get_by_filename(db, psd_path.name)
        if existing:
            print(f"  Ja existe: {psd_path.name} (id={existing['id']})")
            continue

        print(f"Processando: {psd_path.name}")

        meta = derive_template_info(psd_path.name)
        fields = build_editable_fields(psd_path)

        thumb_name = f"{psd_path.stem}.jpg"
        thumb_path = settings.thumbnails_dir / thumb_name
        try:
            generate_preview(psd_path, thumb_path)
            print(f"  Thumbnail: {thumb_path}")
        except Exception as e:
            print(f"  Erro ao gerar thumbnail: {e}")
            thumb_name = None

        t = repo.template_create(
            db,
            filename=psd_path.name,
            display_name=meta["display_name"],
            description=f"Modelo {meta['product_type']} {meta.get('size_cm', '?')}cm",
            size_cm=meta["size_cm"],
            product_type=meta["product_type"],
            editable_fields=fields,
            thumbnail=thumb_name,
        )
        print(f"  Inserido: id={t['id']}, {t['display_name']}")
        print(f"  Campos: {[f['label'] for f in fields]}")

    db.close()
    print("\nCatalogo populado com sucesso!")


if __name__ == "__main__":
    main()
