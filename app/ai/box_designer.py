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

    contato = []
    if telefone:
        contato.append(f"telefone {telefone}")
    if instagram:
        contato.append(f"Instagram {instagram}")
    contato_txt = " e ".join(contato) if contato else "os contatos da marca"

    spec_constraints = ""
    if die_spec:
        canvas = die_spec.get("canvas_px") or {}
        must_not_draw = ", ".join(die_spec.get("prompt_constraints", {}).get("must_not_draw", []))
        spec_constraints = (
            f" Use proporcao exata {die_spec.get('aspect_ratio')}:1, correspondente ao canvas tecnico "
            f"{canvas.get('width')}x{canvas.get('height')} px com sangria inclusa. "
            f"Produza APENAS uma ilustracao retangular full-bleed que sera impressa como fundo da embalagem, "
            f"sem mockup, sem silhueta de caixa, sem fundo branco externo e sem recorte visual. "
            f"Nao coloque a arte dentro de uma pagina, mesa, cartolina, quadro cinza ou prancha tecnica; "
            f"a propria imagem inteira deve ser a arte, preenchida ate os quatro cantos. "
            f"Nao desenhe elementos tecnicos: {must_not_draw}, molde, template, borda de corte, abas brancas, "
            f"linhas pontilhadas, linhas azuis, marcas de registro, paineis, dobras, vincos, contorno da caixa, "
            f"linhas douradas de painel ou simulacao de embalagem aberta. "
            f"A arte deve preencher 100% do retangulo ate a sangria como uma imagem continua, sem areas vazias "
            f"cinzas/brancas nas bordas e sem divisorias internas."
        )

    reference_constraints = ""
    if has_die_guide:
        reference_constraints += (
            " A primeira imagem anexada e um GUIA TECNICO DA FACA: linhas azuis indicam cortes/vincos/limites "
            "e faixas vermelhas indicam AREA PROIBIDA para elementos importantes. Use esse guia apenas para "
            "posicionamento. Nao desenhe linhas azuis, faixas vermelhas, molde ou marcas tecnicas na arte final. "
            "Logo, textos, telefone, Instagram, rostos, simbolos principais e bordas de emblemas devem ficar em "
            "areas limpas, fora das faixas vermelhas e com folga visual."
        )
    if has_client_references:
        if has_die_guide:
            reference_constraints += (
                " As demais imagens anexadas sao referencias do cliente."
            )
        else:
            reference_constraints += " As imagens anexadas sao referencias do cliente."
        if critical_content_by_code:
            reference_constraints += (
                " Use a referencia como identidade visual principal: interprete cores, estilo, mascote, simbolo, "
                "personagem ou logo como parte da arte. Preserve de forma reconhecivel o sinal visual nao-textual "
                "do logo: silhueta, composicao, formas principais, cores e tema grafico. Se houver um simbolo "
                "como pizza, folhas, mascote ou emblema, transforme esse simbolo em elemento visual premium "
                "integrado ao fundo, bem posicionado em area limpa, longe das bordas e longe de cortes/vincos. "
                "Nao copie textos, nomes, letras, telefones, arrobas ou slogans da referencia."
            )
        else:
            reference_constraints += (
                " Use a referencia do cliente como prioridade visual: preserve identidade, cores, estilo, logo "
                "e elementos principais quando existirem. Nao invente um logo diferente se houver logo na imagem; "
                "nao use apenas o nome da marca para criar uma marca nova."
            )
    if not reference_constraints:
        reference_constraints = (
            " Como nao ha imagem de referencia do cliente, crie a identidade visual a partir dos dados fornecidos."
        )

    critical_content_rule = ""
    if critical_content_by_code:
        critical_content_rule = (
            " Nao escreva nenhum texto real, nome da marca, telefone, Instagram, slogan, placa, faixa, etiqueta, "
            "selo de marca ou qualquer bloco de informacao. "
            "Esses elementos serao adicionados depois por software dentro de areas seguras da faca. "
            "Pode reinterpretar o simbolo visual nao-textual do logo enviado como parte da ilustracao, mas sem "
            "copiar letras ou palavras do arquivo de referencia. "
            "Deixe algumas areas limpas e contrastadas para receber a marca e os contatos, mas sem placeholder "
            "textual, sem letras inventadas, sem palavras e sem marca falsa. A arte gerada deve funcionar como "
            "fundo ilustrado premium, com elementos decorativos distribuidos pelos paineis."
        )
        subject = f"uma pizzaria de {product}"
    else:
        critical_content_rule = (
            f" Elementos obrigatorios: um LOGO CENTRAL grande e marcante da '{brand}'; "
            f"fotos apetitosas de {product}; o slogan \"{frase}\"; e um bloco de contato legivel com "
            f"{contato_txt} (use icones de WhatsApp e Instagram)."
        )
        subject = f"a marca '{brand}'"

    return (
        f"Crie uma arte grafica profissional de fundo para embalagem de {product} para {subject}, "
        f"como uma imagem retangular continua full-bleed para impressao. "
        f"Estilo: moderno, vibrante, apetitoso, alta qualidade grafica, pronto para impressao. "
        f"{critical_content_rule} "
        f"Use {tema}. Orientacao horizontal. "
        f"{spec_constraints} "
        f"{reference_constraints}"
    )
