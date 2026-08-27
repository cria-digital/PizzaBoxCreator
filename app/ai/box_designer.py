"""Builds the image-generation prompt for a client-approval box preview.

Takes an order's client + template + edit data and produces a prompt for the Gemini image
model (see app.ai.providers.image_generation). The result is a polished mockup for the client
to approve over WhatsApp — NOT a print file (that stays CMYK/die-cut, generated after approval).
"""

from __future__ import annotations

from app.models.commands import TemaFundo

_TEMA_DESC = {
    TemaFundo.premium.value: "fundo escuro premium (preto/elegante) com acentos vibrantes",
    TemaFundo.tradicional.value: "fundo kraft tradicional (tons quentes de papelao) e aconchegante",
}


def build_box_prompt(
    client: dict,
    template: dict,
    edit_data: dict,
    die_spec: dict | None = None,
    *,
    has_die_guide: bool = False,
    has_client_references: bool = False,
    critical_content_by_code: bool = False,
) -> str:
    """Compose the generation prompt from the order's real data."""
    brand = client.get("name") or "Pizzaria"
    product = template.get("product_type") or "pizza"
    telefone = edit_data.get("telefone") or client.get("phone") or ""
    instagram = edit_data.get("instagram") or client.get("instagram") or ""
    frase = edit_data.get("frase") or "Feito com amor, para voce!"
    tema = _TEMA_DESC.get(edit_data.get("tema_fundo"), "paleta elegante a seu criterio")

    proporcao = die_spec.get("aspect_ratio") if die_spec else edit_data.get("aspect_ratio", "16:9")
    sangria_mm = _bleed_mm(die_spec)
    referencia = edit_data.get("referencia") or edit_data.get("descricao") or tema
    if has_client_references:
        referencia += (
            ". Use as imagens anexadas como referencia visual do cliente, principalmente logo, simbolo, "
            "cores, estilo e composicao."
        )

    spec_constraints = []
    if die_spec:
        canvas = die_spec.get("canvas_px") or {}
        must_not_draw = ", ".join(die_spec.get("prompt_constraints", {}).get("must_not_draw", []))
        spec_constraints.extend([
            f"- Proporcao tecnica da faca: {die_spec.get('aspect_ratio')}:1.",
            f"- Canvas tecnico com sangria: {canvas.get('width')}x{canvas.get('height')} px.",
            "- Arte plana full-bleed para impressao.",
            "- A propria imagem inteira deve ser a arte plana que sera impressa, preenchida ate os quatro cantos.",
            "- Nao coloque a arte dentro de pagina, mesa, cartolina, quadro cinza, prancha tecnica, mockup 3D, foto de caixa pronta, flyer, card de site, banner ou post de rede social.",
            f"- Nao desenhe elementos tecnicos: {must_not_draw}, molde, template, borda de corte, abas brancas, linhas pontilhadas, linhas azuis, marcas de registro, paineis, dobras, vincos, contorno da caixa ou simulacao de embalagem aberta.",
            "- A arte deve preencher 100% do retangulo ate a sangria como uma imagem continua, sem areas vazias cinzas/brancas nas bordas e sem divisorias internas.",
        ])

    reference_constraints = []
    if has_die_guide:
        reference_constraints.extend([
            "- A primeira imagem anexada e um GUIA TECNICO DA FACA: linhas azuis indicam cortes/vincos/limites e faixas vermelhas indicam area proibida para elementos importantes.",
            "- Use esse guia apenas para posicionamento. Nao desenhe linhas azuis, faixas vermelhas, molde ou marcas tecnicas na arte final.",
            "- Logo, textos, telefone, Instagram, rostos, simbolos principais e bordas de emblemas devem ficar em areas limpas, fora das faixas vermelhas e com folga visual.",
        ])
    if has_client_references:
        reference_constraints.extend([
            "- Use as imagens anexadas como referencias do cliente.",
            "- Use o logotipo fornecido exatamente como esta, sem redesenhar nem alterar cores.",
            "- Preserve a identidade visual do logo: silhueta, composicao, formas principais, cores e tema grafico.",
            "- Nao invente um logo diferente e nao use apenas o nome da marca para criar uma marca nova.",
        ])
    else:
        reference_constraints.append("- Como nao ha imagem de referencia do cliente, crie a identidade visual a partir dos dados fornecidos.")

    pipeline_note = ""
    if critical_content_by_code:
        pipeline_note = (
            "\n\nNOTA DO PIPELINE\n"
            "A aplicacao podera recompor logo, telefone, Instagram e textos por codigo depois da geracao. "
            "Mesmo assim, raciocine pela arte completa da caixa: reserve areas limpas e bem compostas para essas informacoes."
        )

    return (
        "Voce e designer grafico especializado em embalagens de pizza.\n"
        "Crie a arte COMPLETA para a tampa de uma caixa de pizza, em uma unica imagem\n"
        f"com proporcao exata {proporcao}:1 (formato horizontal deitado).\n\n"
        "DADOS DA PIZZARIA\n"
        f"Nome: {brand}\n"
        f"Produto: {product}\n"
        f"Slogan: {frase or '(sem slogan)'}\n"
        f"Telefone: {telefone}\n"
        f"Instagram: {instagram}\n\n"
        "REFERENCIA DE ESTILO\n"
        f"{referencia}\n\n"
        "REGRAS OBRIGATORIAS\n"
        "- Use o logotipo fornecido EXATAMENTE como esta, sem redesenhar nem alterar cores.\n"
        "- Escreva o telefone e o Instagram com precisao absoluta, caractere por caractere.\n"
        f"- Deixe {sangria_mm}mm de respiro em todas as bordas: nenhum texto ou elemento\n"
        "  importante encostando nas bordas da imagem, porque essa area sera cortada.\n"
        "- Nao desenhe linhas de corte, dobra, miras de registro ou molde da caixa.\n"
        "- Cores chapadas e contraste alto. Impressao em papelao, sem meios-tons sutis.\n"
        "- Sem gradientes finos, sem sombras suaves, sem texto menor que 3% da altura.\n\n"
        "REGRAS TECNICAS DO SISTEMA\n"
        + "\n".join(spec_constraints + reference_constraints)
        + pipeline_note
    )


def _bleed_mm(die_spec: dict | None) -> float:
    if not die_spec:
        return 3.0
    bleed = die_spec.get("bleed_mm") or {}
    values = [float(v) for v in bleed.values() if isinstance(v, int | float)]
    return round(max(values), 2) if values else 3.0
