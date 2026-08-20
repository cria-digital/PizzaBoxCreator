# Guia de Preparação de Gabarito (PSD)

Como transformar um arquivo de arte da fábrica (geralmente um PSD **achatado** exportado do
CorelDRAW) no gabarito de camadas que o Pizza Box Agent edita automaticamente.

Você faz isso **uma vez por modelo de caixa**. Depois disso, o sistema preenche telefone,
instagram, frase e logo de qualquer cliente — nas duas faces — sem reabrir o Photoshop.

---

## 1. Por que isso é necessário

O sistema não "adivinha" onde fica cada coisa na arte. Ele procura **camadas com nomes
específicos** e troca o conteúdo delas. Um PSD achatado (1 camada só) não tem onde escrever —
por isso o arquivo precisa ser reconstruído com camadas separadas e nomeadas.

> Como conferir se um PSD está achatado: abra no Photoshop. Se o painel **Camadas** mostra só
> uma camada (normalmente "Plano de fundo"/"Background"), ele precisa de preparação.

---

## 2. Nomes de camada obrigatórios

Os nomes são **exatos** (maiúsculas, sublinhados e acentos como abaixo). Organize em grupos só
pra ficar limpo — o que importa pro sistema é o nome de cada camada.

### Caixa DUPLA (duas faces espelhadas)

A maioria das caixas tem duas faces iguais. Cada campo editável precisa de **uma camada por
face**: a face 1 usa o nome base, a face 2 acrescenta `_2` (e `_3`, `_4`… se houver mais faces).

| Grupo sugerido      | Camada               | Tipo        | O que é                                  |
|---------------------|----------------------|-------------|------------------------------------------|
| `FONDOS_TEMATICOS`  | `fundo_kraft_tradicional` | Imagem | Fundo kraft (visível por padrão)         |
|                     | `fundo_preto_premium`     | Imagem | Fundo preto premium (oculto por padrão)  |
| `DECORACOES_OPCIONAIS` | `selo_entrega_rapida`  | Imagem | Selo de entrega (oculto por padrão)      |
|                     | `ilustracao_forno_lenha`  | Imagem | Ilustração de forno (oculto por padrão)  |
| `ELEMENTOS_GRAFICOS`| `LOGO_CLIENTE`        | Imagem      | Área da logo — **face 1**                |
|                     | `LOGO_CLIENTE_2`     | Imagem      | Área da logo — **face 2**                |
| `TEXTOS_EDITAVEIS`  | `TEXTO_TELEFONE`     | Texto       | Telefone — face 1                        |
|                     | `TEXTO_TELEFONE_2`   | Texto       | Telefone — face 2                        |
|                     | `TEXTO_INSTAGRAM`    | Texto       | Instagram — face 1                       |
|                     | `TEXTO_INSTAGRAM_2`  | Texto       | Instagram — face 2                       |
|                     | `TEXTO_FRASE_OPCIONAL`   | Texto   | Frase personalizada — face 1             |
|                     | `TEXTO_FRASE_OPCIONAL_2` | Texto   | Frase personalizada — face 2             |
| `FACAS_E_CORTES`    | (qualquer nome)      | —           | Linhas de faca/corte — **bloqueie o grupo** |

### Caixa de face única

Se o modelo tem só uma face, use **apenas os nomes base** (sem `_2`). O sistema funciona
normalmente — só não duplica nada.

---

## 3. Regras de cada tipo de camada

**Camadas de texto (`TEXTO_*`)**
- Devem ser **camadas de texto de verdade** (ferramenta Texto), não imagem rasterizada.
- Use **texto de parágrafo** (clique e arraste uma caixa), não texto de ponto. Isso define a
  largura/altura da área e ajuda o aviso de "texto não cabe".
- Deixe um conteúdo de exemplo (ex.: "(11) 99999-9999"). O sistema substitui na hora.
- Defina a **cor** que o texto deve ter na caixa — o sistema preserva a cor da camada.

**Camadas de imagem (`LOGO_CLIENTE*`)**
- Crie uma camada (pode ser um retângulo/placeholder) do **tamanho e na posição** onde a logo
  do cliente deve aparecer. O sistema encaixa a logo dentro dessa área, mantendo a proporção.
- Quanto maior a área, maior a logo. Não use 150×150 num arquivo de 4000px — fica minúsculo.

**Fundos e decorações**
- `fundo_kraft_tradicional` **visível**; `fundo_preto_premium` **oculto**. O sistema alterna
  conforme o tema escolhido.
- `selo_entrega_rapida` e `ilustracao_forno_lenha` **ocultos** — o sistema liga quando o
  cliente pede.

**Facas e cortes**
- Mantenha num grupo **bloqueado** (`FACAS_E_CORTES`). O sistema não mexe nele.

---

## 4. Especificações técnicas

- **Resolução:** 300 DPI no tamanho real da caixa (com sangria/bleed, como a fábrica pede).
- **Modo de cor do gabarito:** trabalhe em **RGB**. O sistema gera o **CMYK de produção**
  automaticamente na aprovação, usando o perfil **U.S. Web Coated (SWOP) v2**.
  Não entregue o gabarito já em CMYK achatado.
- **Formato:** salve como **.psd** (ou .psb se for muito grande). Achate **nada** — preserve
  as camadas.
- **Fontes:** o **preview** do WhatsApp usa Arial do sistema (aproximação). O texto fica na
  posição e tamanho certos, mas a fonte exata aparece no arquivo final de produção. Se a fonte
  for crítica, combine com a equipe de impressão.

---

## 5. Passo a passo (Photoshop)

1. Abra o arquivo da fábrica. Se vier achatado, recrie a estrutura sobre a arte existente.
2. Crie os **grupos** e, dentro deles, as **camadas com os nomes exatos** da seção 2.
3. Para cada texto: ferramenta Texto → desenhe a caixa na posição aproximada → digite um
   exemplo → ajuste cor/fonte. Renomeie a camada (`TEXTO_TELEFONE`, etc.).
4. Para a logo: crie a área (`LOGO_CLIENTE`) no tamanho certo. Duplique para a face 2 e renomeie
   `LOGO_CLIENTE_2`.
5. Duplique os textos para a face 2 e renomeie com `_2`.
6. Confira fundos (1 visível, 1 oculto) e decorações (ocultas).
7. Bloqueie o grupo de facas.
8. Salve como `.psd`. **Não achate.**

> Dica: a **posição não precisa ser perfeita** no Photoshop. O ajuste fino você faz depois,
> visualmente, na ferramenta de calibração do sistema (seção 6). O essencial é que as camadas
> existam, com os nomes certos e do tipo certo (texto vs imagem).

---

## 6. Subir no sistema e calibrar

1. No painel, vá em **Catálogo → Upload Template** e envie o `.psd`.
2. No card do modelo, clique em **Calibrar campos**.
3. Arraste e redimensione cada caixa sobre a arte:
   - Telefone, Instagram, Frase e Logo aparecem como caixas — uma por face
     (ex.: "Telefone" e "Telefone (2)").
   - Use o canto inferior direito de cada caixa para redimensionar.
   - Ajuste o **tamanho da fonte** de cada texto no painel lateral.
4. Clique em **Salvar calibração**. A partir daí, todos os previews e arquivos de produção
   desse modelo usam essas posições.
5. Crie um pedido de teste (telefone + logo de exemplo), gere o preview e confira se tudo caiu
   no lugar nas duas faces.

---

## 7. Checklist final

- [ ] Arquivo tem camadas (não está achatado)
- [ ] Todos os nomes exatos da seção 2 existem
- [ ] Textos são camadas de texto (parágrafo), com cor definida
- [ ] `LOGO_CLIENTE` (e `_2`) dimensionados na área real da logo
- [ ] Duas faces = camadas `_2` presentes (ou face única = só nomes base)
- [ ] Fundo kraft visível, premium oculto; decorações ocultas
- [ ] Grupo de facas bloqueado
- [ ] RGB, 300 DPI, salvo como `.psd` sem achatar
- [ ] Upload feito e **calibração salva** no sistema
- [ ] Pedido de teste conferido nas duas faces
