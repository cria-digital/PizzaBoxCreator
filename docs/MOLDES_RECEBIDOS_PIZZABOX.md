# Moldes recebidos - Pizza Box

Fonte dos arquivos analisados:

```text
Pasta local de materiais recebidos: Downloads/Pizzabox/
```

Estes arquivos sao material de producao/referencia e nao devem ser versionados no Git.

## Leitura tecnica

Os arquivos recebidos confirmam que o projeto deve tratar os moldes como arte/faca em
tamanho real para pre-impressao. A IA deve gerar briefing e preview comercial; o arquivo final
de grafica deve ser produzido a partir de molde tecnico aprovado.

## Inventario

| Arquivo | Tipo | Leitura | Dimensao tecnica |
|---|---|---|---|
| `COD. P35 001 - CX. PIZZA 35 PADRAO PIZZA COLOR - DUPLA ITA - 270526.psd` | PSD CMYK achatado | Melhor candidato a piloto P35; arte dupla em tamanho real | 12346 x 6242 px = 89,60 x 45,30 cm a 350 DPI |
| `COD. P35 001 - CX. PIZZA 35 PADRAO PIZZA COLOR - DUPLA ITA - 270525.psd` | PSD CMYK achatado | Versao anterior/proxima do mesmo P35 | 12346 x 6242 px = 89,60 x 45,30 cm a 350 DPI |
| `COD. EG 03 - CX. ESFIHA G ESFIHA PADRAO - 300426 - ok.psd` | PSD CMYK achatado | Molde/base de esfiha grande | 12179 x 6132 px = 88,38 x 44,50 cm a 350 DPI |
| `COD. PA 014 -CX. PIZZA 35 AMERICANA GABI - CLIENTE R7 - DUPLA ITA - 280726 teste fundo.pdf` | PDF CorelDRAW | Arte completa com pagina em escala de producao | 90,76 x 47,05 cm |
| `COD. PA 35 008 - CX. PIZZA ALCAPIZZA 35.pdf` | PDF CorelDRAW | Parece faca/linha tecnica limpa para P35 | 84,78 x 46,17 cm |
| `3 irmaos.cdr.zip` | CorelDRAW zipado | Contem previews internos de paginas/variantes de impressao | precisa abrir no Corel/Illustrator para preflight real |

## Observacoes importantes

- Os tres PSDs grandes sao CMYK e aparecem como uma unica camada de imagem. Eles nao tem camadas
  editaveis para telefone, Instagram, frase ou logo.
- As dimensoes dos PSDs P35 batem com arte dupla em tamanho real a 350 DPI.
- O PDF Alcapizza parece ser o melhor candidato visual para entender a faca/recorte.
- Analise tecnica complementar indicou que os PDFs nao sao PDF/X, usam perfil CMYK
  U.S. Web Coated (SWOP) v2, e a faca nao veio como spot nomeado. As linhas de faca aparecem como
  ciano de processo puro (`C100 M0 Y0 K0`) com aproximadamente 5 pt. As separacoes `/All`
  parecem ser miras/registro, nao `Faca`, `Vinco` ou `Serrilha`.
- Arte e faca vieram como arquivos separados: a arte completa nao contem faca, e o PDF Alcapizza
  nao contem arte.
- A sangria varia por arquivo/modelo. Portanto, sangria e area segura devem ser propriedades do
  template, nao constantes globais do sistema.
- O ZIP Corel traz perfis de cor, incluindo `uswebcoatedswop.icc`, e previews por pagina.

## Decisao de arquitetura

Para producao real, o caminho recomendado e:

1. Escolher um molde piloto, preferencialmente P35 `270526`.
2. Usar a arte recebida como base visual/tamanho real.
3. Versionar a faca como asset imutavel por `template_id`, separada da arte.
4. Confirmar com a grafica se a convencao real de faca e ciano de processo 5 pt ou se deveria ser
   spot/overprint nomeado.
5. Confirmar se o perfil de saida e SWOP v2 mesmo ou FOGRA39.
6. Criar um template tecnico aprovado por modelo.
7. No runtime, o sistema injeta somente dados variaveis: logo, telefone, Instagram, frase e QR.
8. A IA fica limitada a conversa, briefing, leitura de referencia e preview comercial.

## Preflight comercialmente relevante

O piloto deve incluir preflight automatizado para:

- TAC dentro do limite confirmado pela grafica;
- zero objetos RGB no arquivo final;
- imagens efetivas entre 300 e 350 DPI;
- fontes convertidas/incorporadas conforme exigencia da grafica;
- ciano reservado para faca quando essa for a convencao aprovada;
- ausencia de arte invadindo area de seguranca.

## Proximo passo

Piloto recomendado:

```text
P35 270526
```

Entregavel da proxima etapa:

- cadastro tecnico do P35 no sistema;
- imagem plana de preview para aprovacao;
- mapa inicial de campos variaveis;
- validacao manual da faca/recorte com a grafica antes de prometer PDF final pronto para chapa.
