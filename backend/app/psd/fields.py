"""Builds the editable_fields metadata (catalog + order forms) from a PSD's layers.

The "name" of a known field must match an app.models.commands.EditCommand attribute
(telefone, instagram, frase, tema_fundo, adicionar_selo_entrega, adicionar_forno_lenha,
logo_path) -- that's the vocabulary order_service.build_edit_command() reads out of
edit_data. Using the raw PSD layer name instead (e.g. "TEXTO_TELEFONE", "LOGO_CLIENTE")
would silently produce edit_data the engine never applies: it would look filled out in
the catalog/order UI but never actually reach the PSD.
"""

from __future__ import annotations

from pathlib import Path

from app.psd.calibration import split_layer_name
from app.psd.inspector import inspect_template

KNOWN_FIELDS = {
    "TEXTO_TELEFONE": {"name": "telefone", "type": "text", "label": "Telefone"},
    "TEXTO_INSTAGRAM": {"name": "instagram", "type": "text", "label": "Instagram"},
    "TEXTO_FRASE_OPCIONAL": {"name": "frase", "type": "text", "label": "Frase personalizada"},
    "LOGO_CLIENTE": {"name": "logo_path", "type": "image", "label": "Logotipo do cliente"},
    "selo_entrega_rapida": {"name": "adicionar_selo_entrega", "type": "toggle", "label": "Selo entrega rapida"},
    "ilustracao_forno_lenha": {"name": "adicionar_forno_lenha", "type": "toggle", "label": "Ilustracao forno a lenha"},
}

BACKGROUND_LAYERS = ("fundo_kraft_tradicional", "fundo_preto_premium")


def build_editable_fields(template_path: Path) -> list[dict]:
    """Inspect a PSD's layers and return the editable_fields list stored on the template.

    A DUPLA (two-face) box has one layer per field per face (`LOGO_CLIENTE`,
    `LOGO_CLIENTE_2`, ...) -- the engine already mirrors the same content to every face
    (PsdEngine._layers_for), so each face's layer must collapse into a single field here,
    keyed by its base name. Without this, face 2 shows up as its own (non-functional)
    field: its raw layer name doesn't match any EditCommand attribute.
    """
    info = inspect_template(template_path)

    fields = []
    seen_names: set[str] = set()
    backgrounds: set[str] = set()

    for layer in info.layers:
        if not layer.editable:
            continue

        if layer.name in BACKGROUND_LAYERS:
            backgrounds.add(layer.name)
            continue

        base, _face = split_layer_name(layer.name)
        mapping = KNOWN_FIELDS.get(base)
        if mapping:
            if mapping["name"] in seen_names:
                continue
            seen_names.add(mapping["name"])
            fields.append({"required": False, **mapping})
        else:
            if base in seen_names:
                continue
            seen_names.add(base)
            fields.append({
                "name": base,
                "type": "text" if layer.layer_type == "text" else "image",
                "label": base.replace("_", " ").title(),
                "required": False,
            })

    if backgrounds == set(BACKGROUND_LAYERS):
        fields.append({
            "name": "tema_fundo",
            "type": "choice",
            "label": "Tema de fundo",
            "options": ["tradicional", "premium"],
            "required": False,
        })

    return fields
