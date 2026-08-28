"""Builds the image-generation prompt for a client-approval box preview.

Takes an order's client + template + edit data and produces a prompt for the
Gemini image model.

IMPORTANT:
- Gemini generates ONLY the visual artwork/background.
- Logo, slogan and contacts are applied later by the application.
- Technical coordinates are NEVER sent as visible content to the image model.
- This is a client approval preview, NOT the final print file.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.commands import TemaFundo


_TEMA_DESC = {
    TemaFundo.premium.value: (
        "identidade visual premium, sofisticada e marcante, "
        "com base escura, contraste forte e acentos elegantes"
    ),
    TemaFundo.tradicional.value: (
        "identidade visual tradicional e artesanal, "
        "com tons quentes inspirados em papelao kraft, pizzarias classicas "
        "e elementos acolhedores"
    ),
}


@dataclass(frozen=True)
class PizzaBoxTextAgent:
    """Prepares the visual-art prompt for the image-generation agent."""

    client: dict
    template: dict
    edit_data: dict
    die_spec: dict | None = None
    has_die_guide: bool = False
    has_client_references: bool = False
    critical_content_by_code: bool = False

    def build_image_prompt(self) -> str:
        product = self.template.get("product_type") or "pizza"

        tema = _TEMA_DESC.get(
            self.edit_data.get("tema_fundo"),
            (
                "identidade visual profissional, equilibrada e autoral, "
                "com paleta escolhida de acordo com o posicionamento da marca"
            ),
        )

        referencia = (
            self.edit_data.get("referencia")
            or self.edit_data.get("descricao")
            or tema
        )

        if self.has_client_references:
            referencia += (
                ". Use as imagens anexadas somente como referencia visual "
                "para compreender paleta, linguagem grafica, atmosfera, "
                "formas, ilustracoes e personalidade da marca. "
                "Nao redesenhe o logotipo e nao copie textos das referencias."
            )

        spec_constraints = _technical_spec_rules(self.die_spec)

        reference_constraints = _reference_rules(
            has_die_guide=self.has_die_guide,
            has_client_references=self.has_client_references,
        )

        pipeline_note = (
            _pipeline_note()
            if self.critical_content_by_code
            else ""
        )

        return (
            _role_prompt()
            + "\n\n"
            + _objective_prompt(product)
            + "\n\n"
            + "DIRECAO VISUAL DO CLIENTE\n"
            + referencia
            + "\n\n"
            + _art_direction_rules()
            + "\n\n"
            + _logo_visual_rules()
            + "\n\n"
            + _contact_visual_rules()
            + "\n\n"
            + _composition_rules()
            + "\n\n"
            + _forbidden_content_rules()
            + "\n\n"
            + "REGRAS TECNICAS DO SISTEMA\n"
            + "\n".join(spec_constraints + reference_constraints)
            + pipeline_note
        )


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

    return PizzaBoxTextAgent(
        client=client,
        template=template,
        edit_data=edit_data,
        die_spec=die_spec,
        has_die_guide=has_die_guide,
        has_client_references=has_client_references,
        critical_content_by_code=critical_content_by_code,
    ).build_image_prompt()


def _role_prompt() -> str:
    return (
        "Voce e um DIRETOR DE ARTE e DESIGNER GRAFICO SENIOR "
        "especializado em branding, packaging e embalagens para pizzarias.\n"
        "\n"
        "Sua responsabilidade nao e simplesmente preencher um template.\n"
        "Sua responsabilidade e desenvolver um SISTEMA VISUAL COMPLETO, "
        "coeso, profissional, rico e autoral para a embalagem.\n"
        "\n"
        "A arte deve parecer criada por um designer profissional de embalagem, "
        "e nao por um gerador automatico de templates."
    )


def _objective_prompt(product: str) -> str:
    return (
        "OBJETIVO\n"
        f"Produto: {product}\n"
        "\n"
        "Crie exclusivamente a ARTE VISUAL PLANIFICADA de uma caixa de pizza.\n"
        "A imagem inteira deve representar a superficie grafica da embalagem.\n"
        "\n"
        "A orientacao do gabarito e retrato:\n"
        "- parte de baixo da caixa na regiao superior;\n"
        "- parte principal/frontal na regiao inferior.\n"
        "\n"
        "Nao crie flyer, banner, card, anuncio, post de rede social, "
        "pagina de apresentacao ou mockup 3D.\n"
        "\n"
        "O logotipo oficial, slogan, telefone, redes sociais e demais textos "
        "serao aplicados posteriormente pela aplicacao."
    )


def _art_direction_rules() -> str:
    return (
        "DIRECAO DE ARTE\n"
        "\n"
        "- Desenvolva uma identidade visual rica e trabalhada.\n"
        "- Evite composicoes excessivamente simples.\n"
        "- Nao resolva a embalagem apenas com fundo liso + borda + logo central.\n"
        "- Crie profundidade visual por meio da composicao grafica.\n"
        "\n"
        "Dependendo da identidade escolhida, utilize de forma equilibrada:\n"
        "- ilustracoes;\n"
        "- ornamentos;\n"
        "- grafismos;\n"
        "- formas organicas;\n"
        "- massas de cor;\n"
        "- padroes;\n"
        "- texturas graficas;\n"
        "- linhas decorativas;\n"
        "- ingredientes estilizados;\n"
        "- elementos relacionados a pizza e gastronomia;\n"
        "- referencias italianas quando fizerem sentido;\n"
        "- composicoes editoriais;\n"
        "- elementos assimetricos;\n"
        "- repeticoes graficas;\n"
        "- elementos de identidade que atravessem visualmente diferentes regioes.\n"
        "\n"
        "A composicao precisa possuir hierarquia, ritmo, equilibrio, contraste "
        "e uma linguagem visual consistente.\n"
        "\n"
        "Os elementos decorativos devem parecer parte de uma mesma identidade, "
        "e nao objetos independentes colocados aleatoriamente."
    )


def _logo_visual_rules() -> str:
    return (
        "AREA VISUAL DA MARCA\n"
        "\n"
        "Existe uma regiao central no painel principal que recebera "
        "posteriormente o LOGOTIPO OFICIAL do cliente.\n"
        "\n"
        "IMPORTANTE:\n"
        "- NAO desenhe o logotipo.\n"
        "- NAO recrie o logotipo.\n"
        "- NAO invente uma nova marca.\n"
        "- NAO escreva o nome da pizzaria.\n"
        "- NAO coloque um retangulo branco para representar a logo.\n"
        "- NAO crie card branco.\n"
        "- NAO crie placa.\n"
        "- NAO crie placeholder.\n"
        "- NAO desenhe bounding box.\n"
        "- NAO desenhe moldura tecnica em volta da futura logo.\n"
        "\n"
        "O FUNDO DA ARTE DEVE CONTINUAR NATURALMENTE ATRAS DA FUTURA LOGO.\n"
        "\n"
        "A area destinada a marca nao significa uma area vazia ou branca.\n"
        "Ela significa apenas uma regiao com boa leitura e equilibrio visual.\n"
        "\n"
        "Reduza localmente a complexidade quando necessario, mantendo "
        "contraste suficiente para que a marca possa ser aplicada depois.\n"
        "\n"
        "A composicao pode e deve CONVERSAR com a futura marca.\n"
        "\n"
        "Por exemplo:\n"
        "- ornamentos podem contornar a futura marca;\n"
        "- grafismos podem direcionar o olhar para ela;\n"
        "- ilustracoes podem criar uma moldura organica ao redor dela;\n"
        "- padroes podem reduzir de intensidade nessa regiao;\n"
        "- formas podem criar contraste naturalmente;\n"
        "- elementos podem passar visualmente atras da futura marca.\n"
        "\n"
        "Nunca coloque um elemento visual dominante exatamente onde "
        "o logotipo sera aplicado."
    )


def _contact_visual_rules() -> str:
    return (
        "AREA VISUAL DE SLOGAN E CONTATOS\n"
        "\n"
        "Abaixo da regiao principal da marca existe uma area destinada "
        "posteriormente a slogan, telefone, WhatsApp, Instagram e outros contatos.\n"
        "\n"
        "Nao escreva nenhum desses dados.\n"
        "\n"
        "Nao transforme essa area em:\n"
        "- retangulo vazio;\n"
        "- card;\n"
        "- caixa de texto;\n"
        "- placeholder;\n"
        "- painel artificial;\n"
        "- moldura tecnica.\n"
        "\n"
        "O sistema visual da embalagem deve continuar naturalmente nessa regiao.\n"
        "\n"
        "Garanta apenas contraste, respiro e organizacao visual suficientes "
        "para que a aplicacao consiga adicionar posteriormente uma composicao "
        "tipografica profissional.\n"
        "\n"
        "Elementos decorativos podem existir ao redor dessa regiao, desde que "
        "nao prejudiquem a leitura futura."
    )


def _composition_rules() -> str:
    return (
        "COMPOSICAO E HIERARQUIA\n"
        "\n"
        "A arte deve possuir uma hierarquia visual clara:\n"
        "1. futura marca do cliente;\n"
        "2. personalidade visual da pizzaria;\n"
        "3. futura area de slogan e contatos;\n"
        "4. elementos decorativos.\n"
        "\n"
        "A criatividade deve acontecer ao redor das areas funcionais, "
        "sem transformar essas areas em blocos artificiais.\n"
        "\n"
        "Distribua riqueza visual principalmente nas bordas, laterais, cantos "
        "e regioes secundarias, criando caminhos visuais que conduzam o olhar "
        "para o centro da composicao.\n"
        "\n"
        "Evite simetria rigida quando ela deixar o projeto com aparencia generica.\n"
        "Pode utilizar equilibrio assimetrico quando adequado ao conceito.\n"
        "\n"
        "A parte superior e inferior da embalagem devem parecer partes do "
        "MESMO PROJETO GRAFICO.\n"
        "\n"
        "Nao crie dois layouts independentes."
    )


def _forbidden_content_rules() -> str:
    return (
        "CONTEUDO PROIBIDO NA IMAGEM GERADA\n"
        "\n"
        "- nenhum texto;\n"
        "- nenhum numero;\n"
        "- nenhum telefone;\n"
        "- nenhum username;\n"
        "- nenhum @;\n"
        "- nenhum endereco;\n"
        "- nenhum site;\n"
        "- nenhum slogan;\n"
        "- nenhuma palavra decorativa;\n"
        "- nenhum logotipo;\n"
        "- nenhuma tentativa de escrever a marca;\n"
        "- nenhum icone de Instagram;\n"
        "- nenhum icone de WhatsApp;\n"
        "- nenhum QR Code;\n"
        "- nenhuma coordenada;\n"
        "- nenhum valor X ou Y;\n"
        "- nenhum nome de area tecnica;\n"
        "- nenhum texto como 'logo area', 'safe area', 'contact area' ou similar;\n"
        "- nenhuma bounding box;\n"
        "- nenhuma indicacao tecnica.\n"
        "\n"
        "A imagem gerada deve conter SOMENTE elementos graficos e visuais."
    )


def _technical_spec_rules(die_spec: dict | None) -> list[str]:
    rules = [
        "- Gere arte plana full-bleed para impressao.",
        "- A arte deve preencher 100% da imagem ate os quatro cantos.",
        "- Fundos, padroes, texturas e massas de cor devem continuar ate a sangria.",
        "- Nao coloque a arte dentro de uma pagina ou prancha.",
        "- Nao gere mockup 3D ou fotografia de uma caixa pronta.",
        "- Nao gere fundo externo cinza, branco ou bege ao redor da arte.",
        "- Nao gere divisorias artificiais entre os paineis.",
        "- Nao desenhe linhas de corte ou dobra.",
        "- Nao desenhe guias de seguranca.",
        "- Nao escreva informacoes tecnicas.",
        "- Preserve boa legibilidade nas futuras areas de marca e contatos.",
        "- Evite detalhes extremamente sutis que possam desaparecer na impressao em papelao.",
        "- Priorize contraste, formas definidas e uma paleta coerente com a identidade.",
    ]

    if not die_spec:
        return rules

    must_not_draw_items = (
        die_spec
        .get("prompt_constraints", {})
        .get("must_not_draw", [])
    )

    if must_not_draw_items:
        must_not_draw = ", ".join(
            str(item)
            for item in must_not_draw_items
        )

        rules.append(
            f"- Nunca desenhe estes elementos tecnicos: {must_not_draw}."
        )

    return rules


def _reference_rules(
    *,
    has_die_guide: bool,
    has_client_references: bool,
) -> list[str]:
    rules: list[str] = []

    if has_die_guide:
        rules.extend(
            [
                (
                    "- A primeira imagem anexada e um GUIA TECNICO DA FACA "
                    "e serve SOMENTE como referencia espacial."
                ),
                (
                    "- Observe cortes, vincos, dobras, abas, serrilhas "
                    "e regioes estruturalmente delicadas."
                ),
                (
                    "- Nao reproduza visualmente nenhuma linha, cor, faixa, "
                    "texto ou anotacao presente no guia tecnico."
                ),
                (
                    "- Nunca copie coordenadas, numeros ou labels do guia "
                    "para a arte."
                ),
                (
                    "- Elementos decorativos secundarios podem atravessar "
                    "regioes de dobra quando visualmente apropriado, mas "
                    "elementos principais devem permanecer seguros."
                ),
            ]
        )

    if has_client_references:
        rules.extend(
            [
                "- As demais imagens anexadas sao referencias visuais do cliente.",
                (
                    "- Extraia delas somente linguagem visual, paleta, clima, "
                    "estilo, simbolos secundarios e personalidade."
                ),
                "- Nao copie textos existentes nas referencias.",
                "- Nao redesenhe o logotipo existente nas referencias.",
                (
                    "- Nao coloque a imagem de referencia inteira dentro "
                    "da embalagem."
                ),
            ]
        )

    else:
        rules.append(
            "- Como nao existem referencias visuais adicionais do cliente, "
            "desenvolva uma identidade visual original a partir do briefing."
        )

    return rules


def _pipeline_note() -> str:
    return (
        "\n\n"
        "PIPELINE DE COMPOSICAO\n"
        "\n"
        "A aplicacao adicionara posteriormente, de forma deterministica:\n"
        "- logotipo oficial;\n"
        "- slogan;\n"
        "- telefone;\n"
        "- WhatsApp;\n"
        "- Instagram;\n"
        "- site;\n"
        "- endereco;\n"
        "- icones vetoriais.\n"
        "\n"
        "Esses elementos NAO fazem parte da tarefa do agente de imagem.\n"
        "\n"
        "Nao deixe placeholders visiveis para esses elementos. "
        "Apenas organize a composicao para recebe-los naturalmente."
    )


def _bleed_mm(die_spec: dict | None) -> float:
    if not die_spec:
        return 3.0

    bleed = die_spec.get("bleed_mm") or {}

    values = [
        float(v)
        for v in bleed.values()
        if isinstance(v, (int, float))
    ]

    return round(max(values), 2) if values else 3.0