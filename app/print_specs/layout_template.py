"""Normalized composition template for pizza-box AI artwork."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class NormalizedBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    def inset(self, margin_ratio: float) -> "NormalizedBox":
        margin_x = self.width * margin_ratio
        margin_y = self.height * margin_ratio
        return NormalizedBox(
            self.x_min + margin_x,
            self.y_min + margin_y,
            self.x_max - margin_x,
            self.y_max - margin_y,
        )


PIZZA_BOX_STANDARD_01: dict[str, Any] = {
    "id": "pizza_box_standard_01",
    "version": "1.0",
    "showDebugGuides": False,
    "canvas": {
        "width": 1115,
        "height": 2048,
        "coordinate_system": "normalized_0_1",
        "orientation": "portrait",
    },
    "structure": {
        "diecut_locked": True,
        "allow_rotation": False,
        "allow_resize_proportional": True,
        "allow_structure_modification": False,
    },
    "panels": {
        "bottom_panel": {
            "label": "Parte de Baixo",
            "bounds": {"x": 0.035, "y": 0.02, "width": 0.93, "height": 0.50},
            "primary_branding": False,
        },
        "front_panel": {
            "label": "Parte da Frente",
            "bounds": {"x": 0.04, "y": 0.53, "width": 0.92, "height": 0.44},
            "primary_branding": True,
        },
    },
    "fixed_zones": {
        "logo": {
            "panel": "front_panel",
            "locked": True,
            "x_min": 0.18,
            "x_max": 0.82,
            "y_min": 0.61,
            "y_max": 0.755,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "fit": "contain",
            "preserve_aspect_ratio": True,
            "allow_distortion": False,
        },
        "contact_information": {
            "panel": "front_panel",
            "locked": True,
            "x_min": 0.20,
            "x_max": 0.80,
            "y_min": 0.755,
            "y_max": 0.865,
            "horizontal_alignment": "center",
            "vertical_alignment": "center",
            "text_alignment": "center",
        },
    },
    "protected_areas": {
        "cut_lines": True,
        "fold_lines": True,
        "glue_tabs": True,
        "structural_tabs": True,
        "keep_critical_content_outside": True,
    },
    "safe_zone": {
        "critical_content_only_inside_safe_area": True,
        "minimum_internal_margin_ratio": 0.025,
    },
    "generation": {
        "generate_background_artwork": True,
        "generate_logo": False,
        "generate_contact_text": False,
        "reserve_logo_area": True,
        "reserve_contact_area": True,
        "extend_background_to_bleed": True,
        "visual_priority": [
            "logo",
            "brand_identity",
            "contact_information",
            "decorative_elements",
        ],
    },
    "composition": {
        "logo": {
            "source": "customer.logo_asset",
            "render_method": "deterministic_overlay",
            "zone": "template.fixed_zones.logo",
        },
        "contact_information": {
            "source": "customer.contact",
            "render_method": "deterministic_typography",
            "zone": "template.fixed_zones.contact_information",
        },
    },
    "validation": {
        "check_logo_position": True,
        "check_logo_aspect_ratio": True,
        "check_contact_position": True,
        "check_safe_margins": True,
        "check_diecut_integrity": True,
        "check_missing_customer_data": True,
        "reject_invented_information": True,
        "reject_modified_logo": True,
    },
}


def template_zone(name: str, *, inset_safe_margin: bool = True) -> NormalizedBox:
    """Return a fixed normalized zone from the standard pizza-box template."""
    zone = PIZZA_BOX_STANDARD_01["fixed_zones"][name]
    box = NormalizedBox(
        x_min=float(zone["x_min"]),
        y_min=float(zone["y_min"]),
        x_max=float(zone["x_max"]),
        y_max=float(zone["y_max"]),
    )
    if inset_safe_margin:
        margin = float(PIZZA_BOX_STANDARD_01["safe_zone"]["minimum_internal_margin_ratio"])
        return box.inset(margin)
    return box


def template_prompt_summary() -> str:
    """Compact template contract for the text agent prompt."""
    return (
        "REGRAS VISUAIS DO GABARITO\n"
        "- Crie uma arte vertical de embalagem planificada: parte de baixo acima e frente principal abaixo.\n"
        "- A estrutura fisica da caixa ja existe e nao deve ser desenhada, marcada, rotulada ou reinterpretada.\n"
        "- A marca oficial e os contatos serao aplicados depois pelo motor grafico da aplicacao.\n"
        "- Construa contraste, respiro e suporte visual para a marca e para os contatos sem criar retangulos vazios evidentes.\n"
        "- Nenhum marcador, guia, coordenada, caixa delimitadora, nome de regiao ou texto tecnico deve aparecer na arte."
    )


def design_canvas_px(spec: dict[str, Any]) -> dict[str, int]:
    """Return the visual design canvas used by the reference PDFs."""
    canvas = spec["canvas_px"]
    width = int(canvas["width"])
    height = int(canvas["height"])
    if width > height:
        return {"width": height, "height": width}
    return {"width": width, "height": height}


def print_canvas_px(spec: dict[str, Any]) -> dict[str, int]:
    canvas = spec["canvas_px"]
    return {"width": int(canvas["width"]), "height": int(canvas["height"])}


def is_rotated_design_canvas(spec: dict[str, Any]) -> bool:
    design = design_canvas_px(spec)
    printing = print_canvas_px(spec)
    return design["width"] == printing["height"] and design["height"] == printing["width"]


def rotate_design_to_print(image: Image.Image, spec: dict[str, Any]) -> Image.Image:
    if is_rotated_design_canvas(spec):
        return image.transpose(Image.Transpose.ROTATE_270)
    return image.copy()


def rotate_print_to_design(image: Image.Image, spec: dict[str, Any]) -> Image.Image:
    if is_rotated_design_canvas(spec):
        return image.transpose(Image.Transpose.ROTATE_90)
    return image.copy()
