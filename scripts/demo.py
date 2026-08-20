"""Demo script: simulates the full pipeline without needing the API server."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ai.agent import parse_message_offline
from app.psd.engine import PsdEngine
from app.psd.inspector import inspect_template
from app.psd.renderer import generate_preview

TEMPLATE = Path("gabaritos/caixa_35cm_teste.psd")
OUTPUT_PSD = Path("storage/output/demo.psd")
PREVIEW_JPG = Path("storage/preview/demo.jpg")


def main():
    print("=" * 60)
    print("  PIZZA BOX AGENT — Demo")
    print("=" * 60)

    # 1. Inspect template
    print("\n[1] Template disponivel:")
    info = inspect_template(TEMPLATE)
    print(f"    {info.filename} ({info.width}x{info.height})")
    for l in info.layers:
        if l.editable:
            txt = f' = "{l.current_text}"' if l.current_text else ""
            print(f"    -> {l.layer_type}: {l.name}{txt}")

    # 2. Simulate customer message
    message = (
        "Oi! Quero uma caixa premium com telefone (11) 98888-7777, "
        "instagram @pizzaria_vittoria, frase: \"A Melhor Pizza!\", "
        "com forno a lenha"
    )
    print(f"\n[2] Mensagem do cliente:\n    \"{message}\"")

    # 3. Parse with offline agent
    cmd = parse_message_offline(message)
    print(f"\n[3] Comando extraido:")
    for k, v in cmd.model_dump(exclude_none=True, exclude_defaults=True).items():
        print(f"    {k}: {v}")

    # 4. Edit PSD
    print(f"\n[4] Editando PSD...")
    engine = PsdEngine(TEMPLATE)
    changes = engine.apply(cmd)
    for c in changes:
        print(f"    -> {c}")

    # 5. Save
    engine.save(OUTPUT_PSD)
    print(f"\n[5] PSD salvo: {OUTPUT_PSD} ({OUTPUT_PSD.stat().st_size / 1024:.0f} KB)")

    # 6. Generate preview
    generate_preview(OUTPUT_PSD, PREVIEW_JPG)
    print(f"[6] Preview JPG: {PREVIEW_JPG} ({PREVIEW_JPG.stat().st_size / 1024:.0f} KB)")

    print("\n" + "=" * 60)
    print("  Pipeline completo!")
    print("=" * 60)


if __name__ == "__main__":
    main()
