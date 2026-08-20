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


def build_box_prompt(client: dict, template: dict, edit_data: dict) -> str:
    """Compose the generation prompt from the order's real data."""
    brand = client.get("name") or "Pizzaria"
    product = template.get("product_type") or "pizza"
    telefone = edit_data.get("telefone") or client.get("phone") or ""
    instagram = edit_data.get("instagram") or client.get("instagram") or ""
    frase = edit_data.get("frase") or "Feito com amor, para voce!"
    tema = _TEMA_DESC.get(edit_data.get("tema_fundo"), "paleta elegante a seu criterio")

    contato = []
    if telefone:
        contato.append(f"telefone {telefone}")
    if instagram:
        contato.append(f"Instagram {instagram}")
    contato_txt = " e ".join(contato) if contato else "os contatos da marca"

    return (
        f"Crie um design profissional de embalagem de {product} para a marca '{brand}', "
        f"em layout PLANIFICADO de caixa (com abas de dobra e area de corte nas bordas). "
        f"Estilo: moderno, vibrante, apetitoso, alta qualidade grafica, pronto para impressao. "
        f"Elementos obrigatorios: um LOGO CENTRAL grande e marcante da '{brand}'; "
        f"fotos apetitosas de {product}; o slogan \"{frase}\"; e um bloco de contato legivel com "
        f"{contato_txt} (use icones de WhatsApp e Instagram). "
        f"Use {tema}. Orientacao horizontal. "
        f"Se houver imagem de referencia, use-a APENAS como guia de layout e qualidade — "
        f"NAO copie a marca, o nome nem a arte dela."
    )
