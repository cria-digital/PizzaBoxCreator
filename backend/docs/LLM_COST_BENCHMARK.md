# Comparativo de LLMs - custo-beneficio

Atualizado em 2026-08-20.

## Resumo executivo

Para o Pizza Box Agent, a decisao mais forte agora e separar o uso de IA em tres camadas:

1. Parser de pedido/WhatsApp em JSON estruturado.
2. Analise de imagem/foto quando o cliente enviar referencia visual.
3. Geracao de preview visual para aprovacao.

Resultado dos testes locais:

- Melhor modelo local testado: `qwen2.5:3b`.
- Melhor Llama local testado: `llama3.2:3b`, mas com falso positivo em um campo.
- Modelos 1B testados (`llama3.2:1b` e `gemma3:1b`) nao sao confiaveis para producao.
- Gemini, Claude e OpenAI ainda nao foram executados neste ambiente porque faltam `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` e `OPENAI_API_KEY`.

Recomendacao pratica:

- Desenvolvimento e fallback gratuito: usar `qwen2.5:3b` via Ollama.
- Producao de texto: comparar `qwen2.5:3b` contra Gemini 2.5 Flash-Lite e Claude Haiku 4.5 com 100+ mensagens reais.
- Visao e imagem: manter teste separado com modelo multimodal/API; o Ollama implementado agora cobre somente texto.

## Benchmark local executado

Script usado:

```bash
AI_PROVIDER=ollama OLLAMA_MODEL=<modelo> .venv/bin/python scripts/benchmark_llm_models.py
```

Casos avaliados:

- Pedido completo com telefone, Instagram, tema e selo.
- Pedido tradicional com frase e forno a lenha.
- Instagram sem arroba e pedido de visual escuro/elegante.
- Mensagem fora do escopo que deve ser recusada.

| Modelo | Provider | Casos OK | Acuracia por campo | Latencia media | Latencia maxima | Leitura tecnica |
|---|---|---:|---:|---:|---:|---|
| `qwen2.5:3b` | Ollama local | 4/4 | 100.0% | ~2.5s | ~3.7s | Melhor resultado local; candidato gratuito principal |
| `llama3.2:3b` | Ollama local | 3/4 | 92.9% | ~5.0s | ~13.7s | Bom baseline, mas marcou forno a lenha sem pedido |
| `gemma3:1b` | Ollama local | 1/4 | 71.4% | ~4.8s | ~15.2s | Entende parte do pedido, mas inventa campos |
| `llama3.2:1b` | Ollama local | 0/4 | 14.3% | ~2.6s | ~4.5s | Reprovado para parser de pedido |

Conclusao do teste local: `qwen2.5:3b` deve substituir `llama3.2:3b` como baseline gratuito do projeto.

## Modelos de API a testar

Estes modelos ainda precisam de chave de API para benchmark real:

| Modelo/provedor | Status | Motivo |
|---|---|---|
| Gemini 2.5 Flash-Lite | Pendente | Falta `GEMINI_API_KEY` |
| Gemini 2.5 Flash | Pendente | Falta `GEMINI_API_KEY` |
| Claude Haiku 4.5 | Pendente | Falta `ANTHROPIC_API_KEY` |
| OpenAI GPT-5 mini | Pendente | Falta `OPENAI_API_KEY` e provider OpenAI no app |

## Premissas de custo para texto

Estimativa por chamada de parser de pedido:

- 1.500 tokens de entrada.
- 250 tokens de saida.
- Sem cache.
- Sem batch, exceto onde indicado.

Isso representa uma mensagem real com prompt de sistema, contexto do pedido e resposta JSON curta.

## Custos estimados para texto

| Modelo/provedor | Preco oficial usado | Custo estimado por chamada | Custo estimado por 1.000 chamadas | Observacao |
|---|---:|---:|---:|---|
| Ollama `qwen2.5:3b` local | $0 por token | $0 em API | $0 em API | Custo vira maquina/servidor |
| Gemini 2.5 Flash-Lite Standard | $0.10/M input, $0.40/M output | ~$0.000250 | ~$0.25 | Melhor candidato pago barato para parser |
| Gemini 2.5 Flash-Lite Batch/Flex | $0.05/M input, $0.20/M output | ~$0.000125 | ~$0.13 | Bom para processamento em lote |
| Gemini 2.5 Flash Standard | $0.30/M input, $2.50/M output | ~$0.001075 | ~$1.08 | Melhor candidato multimodal barato |
| Claude Haiku 4.5 | $1/M input, $5/M output | ~$0.002750 | ~$2.75 | Mais caro, mas bom baseline de confiabilidade |
| OpenAI GPT-5 mini | $0.25/M input, $2/M output | ~$0.000875 | ~$0.88 | Pendente adicionar provider OpenAI |

## Custos estimados para imagem/preview

O custo de imagem tende a dominar a conta. Como referencia oficial atual:

| Modelo/provedor | Custo oficial usado | Custo por 1.000 previews | Observacao |
|---|---:|---:|---|
| Gemini 2.5 Flash Image Standard | $0.039 por imagem 1024x1024 | ~$39 | Candidato barato para preview |
| Gemini 2.5 Flash Image Batch/Flex | $0.0195 por imagem | ~$19.50 | Bom se o fluxo puder ser assincrono/lote |

Com o limite atual de 5 previews por pedido, o teto teorico por pedido usando
Gemini 2.5 Flash Image Standard fica em cerca de $0.195 por pedido.

## Custo de rodar LLM local no Railway

Modelo local nao cobra token, mas a infraestrutura cobra.
Pelos precos oficiais do Railway:

- CPU: $20 por vCPU/mes.
- RAM: $10 por GB/mes.
- Storage: $0.15 por GB/mes.

Exemplo simples para um servico Ollama pequeno com 2 vCPU e 4 GB RAM ligado 24/7:

- CPU: 2 * $20 = $40/mes.
- RAM: 4 * $10 = $40/mes.
- Total estimado: ~$80/mes, fora armazenamento e trafego.

Isso so compensa se o volume mensal for alto, se houver exigencia de dados internos, ou se a empresa aceitar operar infraestrutura de modelo.
Para volume baixo/medio, API barata tende a ser mais previsivel.

## Plano de teste ampliado

### Fase 1 - Parser de pedido

Rodar 100+ mensagens reais/sinteticas contra cada candidato:

- `qwen2.5:3b`
- `llama3.2:3b`
- Gemini 2.5 Flash-Lite
- Gemini 2.5 Flash
- Claude Haiku 4.5
- OpenAI GPT-5 mini, se adicionarmos provider

Metricas:

- JSON valido.
- Campos corretos.
- Nao inventar dados.
- Recusar fora do escopo.
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

Comparar modelos de imagem por:

- Fidelidade ao pedido.
- Legibilidade.
- Qualidade comercial.
- Custo por preview aprovado.
- Quantidade media de tentativas ate aprovacao.

## Decisao sugerida

Para defender custo-beneficio com o chefe:

1. Trocar o baseline gratuito de `llama3.2:3b` para `qwen2.5:3b`.
2. Eliminar `llama3.2:1b` e `gemma3:1b` da lista de producao.
3. Rodar benchmark com chaves reais de Gemini/Claude antes de decidir producao.
4. Usar API barata para texto se o volume for baixo/medio.
5. So subir Ollama no Railway se o custo mensal ficar menor que API paga no volume real da empresa.

## Fontes oficiais

- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Claude API pricing: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI GPT-5 mini pricing: https://developers.openai.com/api/docs/models/gpt-5-mini
- Ollama API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Ollama Llama 3.2: https://ollama.com/library/llama3.2
- Railway pricing: https://docs.railway.com/pricing/plans
