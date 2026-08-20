# Comparativo de LLMs - custo-beneficio

Atualizado em 2026-08-20.

## Resumo executivo

Para o Pizza Box Agent, a melhor estrategia nao e escolher um unico modelo para tudo.
O app tem tres necessidades diferentes:

1. Interpretar mensagens de pedido/WhatsApp em JSON estruturado.
2. Analisar foto de caixa/modelo quando o usuario envia imagem.
3. Gerar preview visual para aprovacao do cliente.

Minha recomendacao inicial:

- Texto/conversa: testar primeiro `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `claude-haiku-4-5` e `llama3.2:3b` via Ollama.
- Llama gratuito: bom para prototipo local e para reduzir custo de API, mas em producao ele precisa de servidor proprio; no Railway isso vira custo de CPU/RAM.
- Foto/visao: manter Gemini ou Claude nos testes, porque o Llama local implementado agora cobre apenas texto.
- Preview por IA: trocar o default atual `gemini-3-pro-image` por um modelo de imagem mais barato nos testes, porque imagem domina o custo.

## Premissas para estimativa

Estimativa de uma chamada de parser de pedido:

- 1.500 tokens de entrada.
- 250 tokens de saida.
- Sem cache.
- Sem batch.

Isso representa mensagens reais com prompt de sistema, pedido do cliente e resposta JSON curta.

## Custos estimados para texto

| Modelo/provedor | Preco oficial usado | Custo estimado por chamada | Custo estimado por 1.000 chamadas | Observacao |
|---|---:|---:|---:|---|
| Ollama `llama3.2:3b` local | $0 por token | $0 em API | $0 em API | Custo vira maquina/servidor; mais lento localmente |
| Gemini 2.5 Flash-Lite | $0.05/M input, $0.20/M output | ~$0.000125 | ~$0.13 | Melhor candidato para parser barato |
| Gemini 2.5 Flash | $0.15/M input, $1.25/M output | ~$0.000538 | ~$0.54 | Bom equilibrio para texto + multimodal |
| OpenAI GPT-5.6 Luna | $0.20/M input, $1.20/M output | ~$0.000600 | ~$0.60 | Bom candidato se adicionarmos provider OpenAI |
| Claude Haiku 4.5 | $1/M input, $5/M output | ~$0.002750 | ~$2.75 | Mais caro, mas pode ganhar em confiabilidade |

## Custos estimados para imagem/preview

| Modelo/provedor | Custo oficial aproximado | Custo por 1.000 previews | Observacao |
|---|---:|---:|---|
| Gemini 3 Pro Image (`gemini-3-pro-image`) | $0.134 por imagem 1K/2K | ~$134 | Default atual do app; qualidade alta, custo alto |
| Gemini 3.1 Flash Image | $0.067 por imagem 1K | ~$67 | Meio termo |
| Gemini 3.1 Flash Lite Image | $0.0336 por imagem 1K | ~$33.60 | Melhor candidato para preview barato |
| Gemini 2.5 Flash Image | $0.039 por imagem 1024px | ~$39 | Barato e ja alinhado com fluxo Gemini |

Com o limite atual de 5 previews por pedido, o teto teorico por pedido usando
`gemini-3-pro-image` e cerca de $0.67 so em imagem. Com `gemini-3.1-flash-lite-image`,
o teto cai para cerca de $0.168 por pedido.

## Custo de rodar Llama no Railway

Llama nao cobra token quando rodamos local/self-hosted, mas a infraestrutura cobra.
Pelos precos oficiais do Railway:

- CPU: $20 por vCPU/mes.
- RAM: $10 por GB/mes.

Exemplo simples para um servico Ollama pequeno com 2 vCPU e 4 GB RAM ligado 24/7:

- CPU: 2 * $20 = $40/mes.
- RAM: 4 * $10 = $40/mes.
- Total estimado: ~$80/mes, fora armazenamento e trafego.

Isso so compensa se o volume mensal for alto ou se a empresa quiser controlar os dados/modelo.
Para volume baixo/medio, API barata tende a ser mais previsivel.

## Plano de teste

O repositorio agora tem um script inicial para rodar o benchmark e gerar CSV:

```bash
AI_PROVIDER=ollama OLLAMA_MODEL=llama3.2:3b .venv/bin/python scripts/benchmark_llm_models.py
```

Saida padrao: `temp/llm_benchmark.csv`.

Primeiro teste local com `llama3.2:3b`:

- Casos OK: 3/4.
- Acuracia por campo: 92,9%.
- Latencia nos 4 casos: ~2,9s a ~21,6s por chamada local.
- Principal erro: falso positivo em `adicionar_forno_lenha`.
- Conclusao: bom como baseline gratuito, mas ainda precisa ser comparado com Gemini Flash-Lite/Flash e Claude Haiku.

### Fase 1 - Parser de pedido

Rodar 100 mensagens reais/sinteticas contra cada modelo:

- Pedido completo com nome, telefone, Instagram, tema e observacoes.
- Pedido incompleto.
- Mensagem ambigua.
- Correcao/revisao do cliente.
- Mensagem fora do escopo.

Metricas:

- JSON valido.
- Campos corretos.
- Nao inventar dados.
- Tempo medio de resposta.
- Custo por 1.000 chamadas.

Criterio de aprovacao:

- 95%+ de JSON valido.
- 90%+ de campos essenciais corretos.
- Latencia aceitavel para WhatsApp.
- Custo previsivel.

### Fase 2 - Analise de foto

Comparar Gemini Flash/Flash-Lite e Claude Haiku para:

- Identificar tipo/modelo de caixa.
- Ler dados visiveis.
- Retornar incerteza quando a foto estiver ruim.

Metricas:

- Acerto de modelo.
- Acerto de dados lidos.
- Taxa de falso positivo.
- Tempo medio.

### Fase 3 - Preview visual

Comparar modelos de imagem Gemini:

- `gemini-3-pro-image`
- `gemini-3.1-flash-image`
- `gemini-3.1-flash-lite-image`
- `gemini-2.5-flash-image`

Metricas:

- Fidelidade ao pedido.
- Legibilidade.
- Qualidade comercial.
- Custo por preview aprovado.
- Quantidade media de tentativas ate aprovacao.

## Decisao sugerida

Para defender custo-beneficio:

1. Usar Ollama/Llama local como benchmark gratuito e fallback de desenvolvimento.
2. Testar Gemini 2.5 Flash-Lite como principal candidato para texto barato.
3. Manter Claude Haiku como baseline de qualidade.
4. Reduzir custo de preview trocando o modelo de imagem default para uma variante Flash/Lite se a qualidade for suficiente.
5. So subir Ollama no Railway se o custo mensal ficar menor que API paga no volume real da empresa.

## Fontes oficiais

- OpenAI API pricing: https://developers.openai.com/api/docs/pricing
- Claude API pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini models: https://ai.google.dev/gemini-api/docs/models
- Groq models/API: https://console.groq.com/docs/models
- Ollama API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Ollama Llama 3.2: https://ollama.com/library/llama3.2
- Railway pricing: https://docs.railway.com/pricing/plans
