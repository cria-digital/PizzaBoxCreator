# Pizza Box Agent

Ferramenta de pre-venda para fabricas de caixa de pizza. Recebe dados do cliente (painel ou
WhatsApp), edita gabaritos PSD via PhotoshopAPI, gera previews de aprovacao e exporta CMYK
para producao.

> **Leia o [README.md](README.md) primeiro.** Ele tem instalacao, arquitetura, API completa,
> limitacoes e proximos passos. Este arquivo so guarda o que um assistente de IA precisa saber
> para nao errar ao mexer no codigo.

## Quick Start

```bash
pip install -e ".[dev,gemini]"
cp .env.example .env                     # preencher ADMIN_PASSWORD, SECRET_KEY, chave de IA
python scripts/seed_catalog.py           # popula catalogo com os PSDs de gabaritos/
python -m uvicorn app.main:app --reload  # http://localhost:8000
python -m pytest -q                      # 236 testes
```

## Architecture

```
app/
├── main.py            # FastAPI entry point; lifespan faz ensure_dirs() + init_db()
├── config.py          # Settings (pydantic-settings, le .env)
├── api/               # JSON API, prefixo /api
│   ├── orders.py      #   Lifecycle de pedidos (NUCLEO)
│   ├── catalog.py     #   Catalogo de modelos
│   ├── clients.py     #   Clientes
│   ├── stats.py       #   Metricas do funil + limpeza de arquivos
│   ├── whatsapp.py    #   Webhook da Meta
│   └── routes.py      #   Endpoints LEGADOS (process/templates)
├── web/               # Painel web (Jinja2, HTML server-side)
│   ├── views.py       #   Telas e acoes
│   └── auth.py        #   Login por sessao + lockout
├── services/
│   ├── order_service.py     # preview, ai-preview, approve, CMYK (regra de negocio)
│   ├── logo_service.py      # Tratamento da logo do cliente
│   ├── whatsapp_service.py  # Maquina de conversa do WhatsApp
│   ├── whatsapp_config.py   # Credenciais Meta no banco (aplica sem reiniciar)
│   └── admin_account.py     # Troca de usuario/senha
├── psd/
│   ├── engine.py      # Edicao PSD (PhotoshopAPI) + aplica calibracao
│   ├── renderer.py    # Preview JPG (Pillow)
│   ├── calibration.py # Le geometria das camadas editaveis
│   ├── fields.py      # Definicao dos campos editaveis
│   ├── gabarito_builder.py  # Gabarito a partir de arte plana
│   ├── text_metrics.py      # Medicao de texto / resolucao de fonte
│   ├── inspector.py   # Leitura de camadas
│   └── profiles/      # ICC SWOP para CMYK
├── ai/
│   ├── providers.py   # Camada unica sobre Claude e Gemini (texto/visao/imagem)
│   ├── agent.py       # Parser de mensagem: LLM + fallback offline (regex)
│   ├── vision.py      # Analise de foto de caixa
│   ├── box_designer.py # Prompt do mockup de aprovacao
│   └── prompts.py     # System prompts
├── db/
│   ├── schema.sql     # DDL (7 tabelas)
│   ├── connection.py  # init_db(), get_db()
│   └── repositories.py # CRUD
├── models/commands.py # Todos os Pydantic models
├── integrations/whatsapp_client.py  # Graph API da Meta
└── utils/phone.py     # Normalizacao de telefone BR
```

## Order Workflow

```
draft → preview_sent → approved → production → delivered
             ↓    ↑
           revision
```

Rejeicao cria linha em `order_revisions` e devolve o pedido ao ciclo de preview.

## Regras que NAO podem ser quebradas

1. **Preview por IA nao e arquivo de impressao.** `/ai-preview` gera um mockup RGB (Gemini) para
   o cliente aprovar no WhatsApp. O arquivo de producao e SEMPRE o PSD CMYK do `approve`.
2. **`/ai-preview` custa dinheiro** — cada chamada e uma geracao paga. Nunca chame em loop,
   em teste, ou "so pra conferir".
3. **So o Gemini gera imagem.** `image_generation()` exige `GEMINI_API_KEY` independente de
   `AI_PROVIDER`. Claude nao tem saida de imagem.
4. **Precificacao e pagamento estao fora de escopo** por decisao de produto. Nao propor.
5. **Nao commitar** `.env`, PSDs pesados, `storage/`, `assets/originais/`. Ver `.gitignore`.
6. **A validacao de assinatura do webhook** (`META_APP_SECRET`) nao deve ser desligada.

## Modelos de IA em uso

`app/ai/providers.py`: `claude-haiku-4-5` (texto e visao), `gemini-2.5-flash` (texto e visao),
`settings.gemini_image_model` (imagem, default `gemini-3-pro-image`).

## PSD Template Convention

Guia do designer: `docs/PREPARACAO_GABARITO.md`. Nomes de camada em `gabaritos/`:

- `TEXTO_TELEFONE`, `TEXTO_INSTAGRAM`, `TEXTO_FRASE_OPCIONAL` — TextLayer
- `LOGO_CLIENTE` — ImageLayer
- `fundo_kraft_tradicional`, `fundo_preto_premium` — Fundos (toggle)
- `selo_entrega_rapida`, `ilustracao_forno_lenha` — Decoracoes opcionais
- Caixa dupla: sufixo `_2` nas camadas espelhadas (convencao BASE/BASE_2)

## Calibracao de Campos

Cada template guarda uma `calibration` (JSON na tabela `templates` + arquivo
`<nome>.calibration.json` ao lado do PSD): por camada editavel, a geometria
`{x, y, width, height, font_size}` em pixels do canvas. Posiciona telefone/instagram/frase/logo
sobre as areas reservadas da arte, em vez das posicoes de placeholder do PSD.
`engine.apply(cmd, calibration=...)` aplica a geometria; a UI de arrastar fica em
`/catalogo/{id}/calibrar`.

Coordenadas: `y` e o **topo** da caixa de texto (renderer desenha em `transform_ty - font_size`);
logo usa `center_x`/`center_y` como **canto superior esquerdo**. A calibracao se propaga ao CMYK,
porque o CMYK sai do PSD ja editado.

## Database

SQLite em `storage/pizzabox.db`, criado no boot por `init_db()`. 7 tabelas: `clients`,
`templates`, `orders`, `order_revisions`, `whatsapp_messages`, `whatsapp_config`,
`admin_account`. **Nao ha sistema de migracao** — mudancas de schema via
`CREATE TABLE IF NOT EXISTS` / `ALTER TABLE` no `schema.sql`.

## Key Dependencies

- `PhotoshopAPI` — leitura/escrita PSD/PSB (sem Photoshop instalado)
- `Pillow` — composicao de previews
- `pydantic-settings` — carga do `.env` (`app/config.py`)
- `FastAPI` + `Jinja2` — API e painel
- `bcrypt`, `itsdangerous` — senha e cookie de sessao
- `anthropic` / `google-genai` — providers de IA (import preguicoso)
- SQLite (stdlib)
- Extras opcionais: `[logo]` (rembg, remove fundo da logo), `[gemini]` (SDK Google),
  `[dev]` (pytest)

## Known Limitations

Do motor PSD (`engine.py` / `renderer.py`) — detalhes na secao 12 do README:

- Tipos de camada **descartados** no preview e no CMYK: smart objects, camadas de ajuste,
  shape layers, e efeitos/estilos de camada (sombra, contorno). So Group/Image/Text sao
  compostos. PSDs reais que usam esses recursos saem degradados.
- Camadas de imagem nao-RGB (grayscale/indexed) sao ignoradas
- Preview ignora blend modes, clipping masks e opacidade de grupo
- Preview resolve a fonte real do PSD (registro do Windows / fc-match); so cai em Arial se a
  fonte nao estiver instalada — nesse caso `engine.font_warnings()` avisa
- PhotoshopAPI nao grava merged image data; preview e composto manualmente (Pillow)
- Conversao CMYK usa ICC (SWOP); sem o `.icc` cai no fallback subtrativo (desvio de cor)
- Trabalhar sobre o PSD original (20–500 MB) e lento e pesado a cada preview

Ja resolvidas (antes eram limitacoes): caixa DUPLA via BASE/BASE_2; canais R/G/B fora de ordem
no `get_image_data`.

## Direcao arquitetural

`docs/RELATORIO_DIAGNOSTICO.md` propoe tirar o PSD pesado do caminho critico: usar uma imagem
plana leve por fundo + a calibracao existente para montar previews, e entregar ao designer um
pacote de producao (preview aprovado, logo tratada, textos, posicoes) em vez de outro PSD
gigante. Resolve de uma vez a lentidao e a perda de fidelidade listadas acima.
