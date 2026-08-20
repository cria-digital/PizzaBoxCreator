# Pizza Box Agent

Ferramenta de **pré-venda para fábricas de caixa de pizza**. O cliente (pizzaria) manda os
dados pelo WhatsApp ou pelo painel, o sistema monta a arte sobre um gabarito, gera um
**preview de aprovação** na hora e, quando aprovado, exporta o **arquivo de produção em CMYK**
para a gráfica.

Stack: **Python 3.11+ / FastAPI / SQLite / PhotoshopAPI / Pillow**, com IA (Claude ou Gemini)
para interpretar mensagens, ler fotos de caixas e gerar o mockup de aprovação.

---

## Sumário

1. [Subir o projeto em 5 minutos](#1-subir-o-projeto-em-5-minutos)
2. [O que NÃO está no repositório](#2-o-que-não-está-no-repositório)
3. [Como o sistema funciona](#3-como-o-sistema-funciona)
4. [Mapa do código](#4-mapa-do-código)
5. [Configuração (.env)](#5-configuração-env)
6. [Painel web](#6-painel-web)
7. [API HTTP](#7-api-http)
8. [Banco de dados](#8-banco-de-dados)
9. [Gabaritos e calibração](#9-gabaritos-e-calibração)
10. [WhatsApp](#10-whatsapp)
11. [Testes e scripts](#11-testes-e-scripts)
12. [Limitações conhecidas](#12-limitações-conhecidas)
13. [Estado do projeto e próximos passos](#13-estado-do-projeto-e-próximos-passos)
14. [Documentação complementar](#documentação-complementar)

---

## 1. Subir o projeto em 5 minutos

Requer **Python 3.11 ou superior**.

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Dependências (o extra [dev] traz pytest; [gemini] é necessário para o preview por IA)
pip install -e ".[dev,gemini]"

# 3. Configuração
cp .env.example .env
#    Edite o .env: preencha ADMIN_PASSWORD, SECRET_KEY e pelo menos uma chave de IA.
#    Gere a SECRET_KEY com:
#      python -c "import secrets; print(secrets.token_urlsafe(48))"

# 4. Popular o catálogo com os gabaritos da pasta gabaritos/
python scripts/seed_catalog.py

# 5. Rodar
python -m uvicorn app.main:app --reload
```

Acesse **http://localhost:8000** e faça login com o `ADMIN_USER` / `ADMIN_PASSWORD` do `.env`.

Checagem rápida de saúde: `curl http://localhost:8000/health`

> O banco (`storage/pizzabox.db`) e as pastas de saída são criados sozinhos no primeiro boot
> (`Settings.ensure_dirs()` + `init_db()` em [app/main.py](app/main.py)). Em produção com
> PostgreSQL, rode as migrações Alembic; no Docker isso acontece automaticamente no boot.

### Extras opcionais

| Extra | Comando | Para quê |
|---|---|---|
| `dev` | `pip install -e ".[dev]"` | pytest e cobertura (necessário para rodar os testes) |
| `gemini` | `pip install -e ".[gemini]"` | SDK do Google. **Obrigatório** para o preview de aprovação por IA |
| `logo` | `pip install -e ".[logo]"` | Remoção automática de fundo da logo do cliente (baixa ~170 MB de modelo ONNX no 1º uso) |

Sem o extra `logo`, a logo do cliente é aplicada como veio (com fundo).

### Deploy no Railway

O repositório já inclui `Dockerfile` e `railway.json`. No Railway:

1. Crie um projeto e adicione um banco **Postgres** gerenciado.
2. Adicione um serviço a partir do GitHub `cria-digital/pizza-box-agent`.
3. No serviço do app, configure:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}`
   - `ADMIN_PASSWORD=<senha forte>`
   - `SECRET_KEY=<chave longa gerada>`
   - `SECURE_COOKIES=true`
   - `CORS_ORIGINS=https://<dominio-do-app>`
   - chaves de IA e Meta, quando forem usadas
4. Gere o domínio público do serviço.

O container executa `alembic upgrade head`, popula o catálogo a partir de `gabaritos/` e sobe o
FastAPI na porta `PORT` injetada pelo Railway. O healthcheck configurado é `/health`.

---

## 2. O que NÃO está no repositório

Isto é importante: o repo contém **apenas código e gabaritos leves**. Os itens abaixo precisam
ser obtidos à parte.

| Item | Por que está fora | Como obter |
|---|---|---|
| **`.env`** | Contém chaves de API e senha do painel | Copie de `.env.example` e preencha |
| **Gabaritos PSD pesados** — `caixa_35cm_real.psd` (19 MB), `caixa_p35_mespais.psd` (49 MB), `cod_eg03_esfirra_editavel.psd` (38 MB) | 106 MB de arte proprietária de cliente; incharia o histórico do git para sempre | Entregues à parte (transferência de arquivos). Coloque em `gabaritos/` e rode `python scripts/seed_catalog.py` |
| **`assets/originais/`** (324 MB) | Artes originais dos clientes | Entregues à parte, se necessário |
| **`storage/`** (banco, previews, saídas CMYK) | Dados de runtime, recriados sozinhos | — |
| **Credenciais Meta / WhatsApp** | Segredo do cliente final | Painel do App em developers.facebook.com |

**Os três gabaritos que ESTÃO no repo** são suficientes para rodar e testar o sistema inteiro:

| Arquivo | Tamanho | Uso |
|---|---|---|
| `caixa_35cm_teste.psd` | 218 KB | PSD sintético mínimo, usado pelos testes |
| `caixa_producao_placeholder.psd` | 4,7 MB | Caixa completa de exemplo, com calibração pronta |
| `cod_eg03_premium.psd` | 2,0 MB | Modelo de esfiha, fundo premium |

Os arquivos `*.calibration.json` de **todos** os modelos (inclusive dos pesados) estão
versionados — então, ao receber um PSD pesado, a calibração dele já vem junto.

Se precisar de um PSD do zero: `python scripts/create_test_template.py` gera um sintético.

---

## 3. Como o sistema funciona

### Ciclo de vida do pedido

```
draft ──► preview_sent ──► approved ──► production ──► delivered
              │    ▲
              └────┘
             revisão
      (rejeitado com feedback)
```

1. **draft** — pedido criado com cliente, modelo e dados (telefone, Instagram, frase, logo).
2. **preview_sent** — o sistema gerou um preview e mandou pro cliente aprovar.
3. **approved** — cliente aprovou; o sistema gera o **PSD CMYK de produção**.
4. **production** / **delivered** — controle operacional na gráfica.

Toda rejeição vira uma linha em `order_revisions` com o feedback do cliente, e o pedido volta
para o ciclo de preview.

### Os dois tipos de preview (não confundir)

Esta é a distinção mais importante do sistema:

| | **Preview do gabarito** (`/preview`) | **Preview por IA** (`/ai-preview`) |
|---|---|---|
| Como é feito | Composição real do PSD via PhotoshopAPI + Pillow | Geração de imagem pelo Gemini ("Nano Banana") |
| Fidelidade | Reflete o que vai pra produção | Mockup bonito, **não** é fiel ao arquivo final |
| Custo | Grátis (CPU) | **Cada chamada é uma geração paga** |
| Para quê | Conferência técnica interna | Aprovação rápida do cliente no WhatsApp |
| É arquivo de impressão? | Não (é JPG) — mas o CMYK sai do mesmo PSD editado | **Não, em hipótese nenhuma** |

O **arquivo de impressão** é sempre o PSD CMYK gerado no `approve` — nunca um preview.

### Pipeline de produção

No `approve`, o sistema gera o PSD de produção em **CMYK**, com perfil **ICC (SWOP)** embutido
([app/psd/profiles/uswebcoatedswop.icc](app/psd/profiles/uswebcoatedswop.icc)), carimbado no DPI
de `PRODUCTION_DPI` (padrão 350). Sem o `.icc` disponível, cai num fallback subtrativo — que
funciona, mas com desvio de cor.

---

## 4. Mapa do código

```
app/
├── main.py              # Entry point FastAPI: monta routers, lifespan (ensure_dirs + init_db)
├── config.py            # Settings via pydantic-settings; lê o .env; ensure_dirs()
│
├── api/                 # API HTTP (JSON), prefixo /api
│   ├── orders.py        #   Lifecycle do pedido — é o núcleo do sistema
│   ├── catalog.py       #   Catálogo de modelos + thumbnails
│   ├── clients.py       #   Clientes (upsert por telefone)
│   ├── stats.py         #   Métricas do funil + limpeza de arquivos antigos
│   ├── whatsapp.py      #   Webhook da Meta (GET verificação, POST mensagens)
│   └── routes.py        #   Endpoints LEGADOS (process/templates) — mantidos por compat
│
├── web/                 # Painel web (HTML server-side, Jinja2)
│   ├── views.py         #   Todas as telas e ações do painel
│   └── auth.py          #   Login por sessão (cookie assinado), lockout por tentativas
│
├── services/            # Regra de negócio
│   ├── order_service.py #   preview, ai-preview, approve, geração do CMYK
│   ├── ai_cost_guard.py #   cache e limite de custo para preview de aprovação por IA
│   ├── production_package.py # pacote ZIP para o designer após aprovação
│   ├── logo_service.py  #   Tratamento da logo do cliente (remoção de fundo opcional)
│   ├── whatsapp_service.py  # Máquina de conversa do WhatsApp
│   ├── whatsapp_config.py   # Credenciais Meta salvas no banco (sem reiniciar o app)
│   └── admin_account.py #   Troca de usuário/senha do painel
│
├── psd/                 # Motor gráfico
│   ├── engine.py        #   Edição do PSD (PhotoshopAPI) + aplicação da calibração
│   ├── flat_engine.py   #   Preview rápido via imagem plana + calibração
│   ├── renderer.py      #   Composição do preview JPG (Pillow)
│   ├── calibration.py   #   Lê a geometria das camadas editáveis do PSD
│   ├── fields.py        #   Definição dos campos editáveis
│   ├── gabarito_builder.py  # Monta gabarito a partir de arte plana
│   ├── text_metrics.py  #   Medição de texto e resolução da fonte real do PSD
│   ├── inspector.py     #   Leitura de camadas
│   └── profiles/        #   Perfil ICC SWOP para o CMYK
│
├── ai/
│   ├── providers.py     #   Camada única sobre Claude e Gemini (texto, visão, imagem)
│   ├── agent.py         #   Parser de mensagem: LLM + fallback offline por regex
│   ├── vision.py        #   Análise de foto de caixa (identifica modelo e lê dados)
│   ├── box_designer.py  #   Prompt do mockup de aprovação
│   └── prompts.py       #   System prompts
│
├── db/
│   ├── models.py        #   Modelos SQLAlchemy
│   ├── session.py       #   Engine/session + migrações leves para SQLite local
│   ├── connection.py    #   compat legado para sqlite3 bruto
│   └── repositories.py  #   CRUD de todas as tabelas
│
├── models/commands.py   # Todos os modelos Pydantic
├── integrations/whatsapp_client.py   # Cliente HTTP da Graph API da Meta
├── utils/phone.py       # Normalização de telefone brasileiro
├── templates/*.html     # Telas Jinja2
└── static/              # CSS e JS do painel

scripts/                 # Utilitários de linha de comando (ver seção 11)
tests/                   # 239 testes
docs/                    # Documentação complementar
gabaritos/               # PSDs + calibrações
```

**Ponto de partida para entender o sistema:** leia
[app/services/order_service.py](app/services/order_service.py) — é onde toda a regra de negócio
converge. Depois [app/psd/engine.py](app/psd/engine.py) para o motor gráfico.

---

## 5. Configuração (.env)

Todas as variáveis estão documentadas em [.env.example](.env.example). As **obrigatórias**:

| Variável | Obrigatória | Observação |
|---|---|---|
| `ADMIN_PASSWORD` | ✅ sim | Sem default — o app não sobe sem ela |
| `SECRET_KEY` | ✅ sim | Assina o cookie de sessão |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` ou `AI_PROVIDER=ollama` | ✅ uma opção | Ollama cobre apenas texto; precisa do servidor Ollama rodando |
| `GEMINI_API_KEY` | para `/ai-preview` | **Só o Gemini gera imagem**; obrigatória para o preview de aprovação, mesmo usando Claude no texto |
| `PRODUCTION_DPI` | não (350) | DPI carimbado no arquivo de produção |
| `META_*` | não | WhatsApp desligado se em branco |

Modelos de IA usados hoje ([app/ai/providers.py](app/ai/providers.py)): `claude-haiku-4-5`
(texto e visão), `gemini-2.5-flash` (texto e visão), `GEMINI_IMAGE_MODEL` (imagem)
e `OLLAMA_MODEL` para Llama local/self-hosted em tarefas de texto.

Para testar Llama sem custo de API, instale o Ollama e rode:

```bash
ollama serve
ollama pull llama3.2:3b
AI_PROVIDER=ollama OLLAMA_MODEL=llama3.2:3b python -m uvicorn app.main:app --reload
```

No Railway, `localhost` e gratuito so funcionam se voce tambem subir/ligar um servico Ollama
no mesmo ambiente ou apontar `OLLAMA_BASE_URL` para uma instancia propria.

Antes de expor o app na internet: troque `CORS_ORIGINS=*` por origens explícitas e ligue
`SECURE_COOKIES=true` (exige HTTPS).

---

## 6. Painel web

| Rota | Tela |
|---|---|
| `/` | Dashboard (métricas e pedidos recentes) |
| `/funil` | Funil de pedidos por status |
| `/pedidos/novo` | Criar pedido (inclui análise de foto de caixa por IA) |
| `/pedidos/{id}` | Detalhe: gerar preview, aprovar, rejeitar, enviar por WhatsApp |
| `/clientes` | Clientes |
| `/catalogo` | Modelos: upload de PSD, ativar/desativar, thumbnail, excluir |
| `/catalogo/{id}/calibrar` | **Calibração** — arrastar os campos sobre a arte |
| `/configuracoes/whatsapp` | Credenciais Meta (aplicadas sem reiniciar) |
| `/configuracoes/conta` | Trocar usuário/senha do painel |

Todas exigem login, exceto `/login` e `/health`.

---

## 7. API HTTP

Documentação interativa gerada automaticamente em **`/docs`** (Swagger) com o app rodando.

### Pedidos — o núcleo

| Método | Rota | O que faz |
|---|---|---|
| `POST` | `/api/orders` | Cria pedido (status `draft`) |
| `GET` | `/api/orders` | Lista, com filtros `status` e `client_id` |
| `GET` | `/api/orders/{id}` | Detalhe + histórico de revisões |
| `PATCH` | `/api/orders/{id}` | Atualiza dados |
| `PATCH` | `/api/orders/{id}/status` | Move o status manualmente |
| `POST` | `/api/orders/{id}/preview` | Gera preview do gabarito (grátis) |
| `POST` | `/api/orders/{id}/ai-preview` | Gera mockup por IA (**geração paga**) |
| `POST` | `/api/orders/{id}/approve` | Aprova e gera o PSD CMYK de produção |
| `POST` | `/api/orders/{id}/reject` | Rejeita com feedback (cria revisão) |
| `GET` | `/api/orders/{id}/preview` | Download do preview JPG |
| `GET` | `/api/orders/{id}/production` | Download do PSD CMYK |

### Catálogo, clientes, sistema

| Método | Rota |
|---|---|
| `GET` | `/api/catalog`, `/api/catalog/{id}`, `/api/catalog/{id}/thumbnail` |
| `POST` / `GET` | `/api/clients`, `/api/clients/{phone}` |
| `GET` / `POST` | `/api/stats`, `/api/cleanup/preview`, `/api/cleanup/execute` |
| `GET` / `POST` | `/api/webhooks/whatsapp` (verificação / recepção) |
| `GET` | `/health` — liveness/readiness (status, banco, whatsapp) |

### Legado

`GET /api/templates`, `POST /api/process`, `POST /api/process-upload` — anteriores ao modelo de
pedidos. Mantidos por compatibilidade; **não use em código novo**.

---

## 8. Banco de dados

Por padrão, usa SQLite em `storage/pizzabox.db`; em produção, use PostgreSQL via
`DATABASE_URL`. O schema canônico está nos modelos SQLAlchemy e nas migrações Alembic em
`alembic/versions/`. O boot local cria tabelas ausentes e aplica migrações aditivas pequenas para
SQLite existente.

| Tabela | Conteúdo |
|---|---|
| `clients` | Pizzarias (chave natural: telefone normalizado) |
| `templates` | Modelos do catálogo + **`calibration`** (JSON com a geometria dos campos) |
| `orders` | Pedidos e seus dados |
| `order_revisions` | Histórico de previews/rejeições, com origem (`flat`, `psd`, `ai`) |
| `whatsapp_messages` | Log de mensagens (entrada e saída) |
| `whatsapp_config` | Credenciais Meta configuradas pelo painel |
| `admin_account` | Usuários/senhas do painel (hash bcrypt) |
| `audit_log` | Trilha de auditoria de criação, aprovação e rejeição |

Para PostgreSQL:

```bash
alembic upgrade head
```

No `docker-compose.yml`, o app executa `alembic upgrade head` antes de iniciar o servidor.

---

## 9. Gabaritos e calibração

### Convenção de nomes de camada

O guia completo para o designer está em
[docs/PREPARACAO_GABARITO.md](docs/PREPARACAO_GABARITO.md). Resumo:

| Camada | Tipo | Papel |
|---|---|---|
| `TEXTO_TELEFONE`, `TEXTO_INSTAGRAM`, `TEXTO_FRASE_OPCIONAL` | TextLayer | Textos editáveis |
| `LOGO_CLIENTE` | ImageLayer | Logo do cliente |
| `fundo_kraft_tradicional`, `fundo_preto_premium` | Qualquer | Fundos (liga/desliga) |
| `selo_entrega_rapida`, `ilustracao_forno_lenha` | Qualquer | Decorações opcionais |

Para **caixa dupla**, use o sufixo `_2` nas camadas espelhadas (convenção BASE / BASE_2).

### Calibração

Cada template guarda um JSON `calibration` (na tabela `templates` e num arquivo
`<nome>.calibration.json` ao lado do PSD) com a geometria de cada campo editável em pixels do
canvas: `{x, y, width, height, font_size}`.

Isso existe porque as posições de placeholder do PSD raramente coincidem com as áreas reservadas
da arte. A UI de arrastar fica em `/catalogo/{id}/calibrar` (botão **"Calibrar campos"** no
catálogo).

Detalhes de coordenadas:

- `y` é o **topo** da caixa de texto (o renderer desenha em `transform_ty - font_size`)
- a logo usa `center_x` / `center_y` como **canto superior esquerdo**
- a calibração se propaga ao CMYK, porque o CMYK é gerado a partir do PSD já editado

---

## 10. WhatsApp

Integração com a **WhatsApp Business API (Meta / Graph API)**. Fica desligada enquanto
`META_WHATSAPP_TOKEN` e `META_PHONE_NUMBER_ID` estiverem vazios.

**Configuração:** pela tela `/configuracoes/whatsapp` (salva no banco, aplica sem reiniciar) ou
pelas variáveis `META_*` no `.env`. O webhook do App na Meta deve apontar para
`https://<seu-host>/api/webhooks/whatsapp` — precisa de **HTTPS público** (use ngrok em dev).

**Fluxo da conversa** ([app/services/whatsapp_service.py](app/services/whatsapp_service.py)):
o cliente recebe o catálogo → escolhe o modelo → manda os dados e a logo → recebe o preview →
responde aprovando ou pedindo ajuste → aprovado, o pedido segue para produção.

A assinatura dos webhooks é validada com `META_APP_SECRET` — não desligue essa verificação.

---

## 11. Testes e scripts

```bash
pip install -e ".[dev]"
python -m pytest -q                    # suíte completa
python -m pytest --cov=app             # com cobertura
python -m pytest tests/test_api_orders.py -v
```

**Estado atual: 239 testes, todos passando.** A suíte não faz chamada de rede — as chamadas de
IA e da Meta são mockadas.

### Scripts utilitários (`scripts/`)

| Script | Para quê |
|---|---|
| `seed_catalog.py` | Popula o catálogo com os PSDs de `gabaritos/`. **Rode após adicionar um gabarito** |
| `create_test_template.py` | Gera um PSD sintético mínimo para testes |
| `test_workflow.py` | Testa o fluxo completo contra um servidor rodando (precisa do extra `dev`) |
| `build_gabarito_from_flat.py` | Monta um gabarito a partir de uma arte plana |
| `create_premium_gabarito.py`, `create_simulado_producao.py`, `create_placeholder_producao.py` | Geradores de gabaritos de exemplo |
| `whatsapp_send_test.py` | Envia uma mensagem de teste pela API da Meta |
| `demo.py` | Demonstração do fluxo |
| `backup.sh` | Backup manual de SQLite ou PostgreSQL |
| `smoke_railway.py` | Valida uma URL publicada do Railway (`/health`, login, métricas e catálogo) |

---

## 12. Limitações conhecidas

Limitações **reais e atuais** do caminho legado via PSD ([engine.py](app/psd/engine.py) /
[renderer.py](app/psd/renderer.py)). Leia antes de prometer qualquer coisa ao cliente:

- **Tipos de camada descartados.** Smart objects, camadas de ajuste, shape layers e
  efeitos/estilos de camada (sombra, contorno) **são perdidos** no preview e no CMYK. Só
  `Group`, `Image` e `Text` são compostos. PSDs reais que usam esses recursos saem degradados.
- **Camadas de imagem não-RGB** (grayscale, indexed) são ignoradas.
- **Blend modes, clipping masks e opacidade de grupo** são ignorados no preview.
- **Fontes.** O preview resolve a fonte real do PSD (registro do Windows / `fc-match`); se a
  fonte não estiver instalada no servidor, cai em Arial e `engine.font_warnings()` avisa.
- **Merged image data.** A PhotoshopAPI não grava o composto do PSD; o preview é montado
  manualmente com Pillow.
- **CMYK.** Usa ICC (SWOP) por padrão; sem o `.icc`, o fallback subtrativo desvia a cor.
- **Peso.** Trabalhar sobre o PSD original (arquivos de 20–500 MB) é lento e consome muita
  memória e disco a cada preview. O caminho novo via `*_flat.png` evita esse problema para
  templates que tenham imagem plana cadastrada.

Já resolvido (não é mais limitação): caixa **dupla** via convenção `BASE` / `BASE_2`; ordem dos
canais R/G/B no `get_image_data`.

---

## 13. Estado do projeto e próximos passos

### O que está pronto e funcionando

Ciclo completo do pedido, catálogo, clientes, revisões, painel web, calibração, parser de
mensagem por IA, análise de foto de caixa, preview de aprovação por IA com cache/limite de
custo, preview rápido por imagem plana, geração CMYK no caminho legado PSD, pacote ZIP para o
designer, Docker/PostgreSQL, backup, auditoria, métricas Prometheus e 239 testes passando.

### Arquitetura operacional recomendada

O caminho preferencial para novos modelos é usar uma imagem plana (`*_flat.png` ou variantes
`*_flat_kraft.png` / `*_flat_premium.png`) mais calibração visual. O PSD continua como fallback
legado. Na aprovação, o sistema entrega um pacote de produção ao designer com preview aprovado,
logo, arte plana e JSON de posições. Veja
[docs/ARQUITETURA_OPERACIONAL.md](docs/ARQUITETURA_OPERACIONAL.md).

### Pendências externas (bloqueiam a conclusão)

1. **Credenciais Meta / WhatsApp Business** do cliente final.
2. **Arquivos de faca** de cada modelo, com a gráfica — para o fechamento gráfico preciso.
3. **Hospedagem com HTTPS público** — o webhook do WhatsApp não funciona sem isso.

### Fora de escopo (decisão de produto)

**Precificação e pagamento** estão intencionalmente fora do escopo. A ferramenta é de pré-venda.

---

## Documentação complementar

| Documento | Público |
|---|---|
| [docs/PREPARACAO_GABARITO.md](docs/PREPARACAO_GABARITO.md) | **Designer** — como preparar o PSD |
| [docs/ARQUITETURA_OPERACIONAL.md](docs/ARQUITETURA_OPERACIONAL.md) | Arquitetura atual, deploy e pendências |
| [docs/GO_LIVE_CHECKLIST.md](docs/GO_LIVE_CHECKLIST.md) | Checklist de deploy, variáveis e validação |
| [docs/RELATORIO_DIAGNOSTICO.md](docs/RELATORIO_DIAGNOSTICO.md) | Diagnóstico técnico e proposta de mudança |
| [RELATORIO_STATUS.md](RELATORIO_STATUS.md) | Status do projeto em linguagem de negócio |
| [CLAUDE.md](CLAUDE.md) | Contexto para assistentes de IA que trabalhem no repo |
