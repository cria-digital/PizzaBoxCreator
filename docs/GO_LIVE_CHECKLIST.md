# Go-live checklist - Pizza Box Agent

Use este checklist para subir e validar o app no Railway sem pular etapas.

## 1. Railway

- Workspace: CRIA Digital.
- Projeto: `pizza-box-agent`.
- Ambiente: `production`.
- Postgres: online.
- Schema aplicado: `alembic_version = 2e9c4d6a1b7f`.
- App service: conectado ao GitHub `cria-digital/pizza-box-agent`, branch `main`.

## 2. Variaveis do app

Obrigatorias para subir:

```text
DATABASE_URL=${{ Postgres.DATABASE_PRIVATE_URL }}
ADMIN_USER=admin
ADMIN_PASSWORD=<senha-forte>
SECRET_KEY=<chave-longa>
SECURE_COOKIES=false
CORS_ORIGINS=*
```

Depois que a URL publica estiver validada:

```text
SECURE_COOKIES=true
CORS_ORIGINS=https://<url-publica-do-railway>
```

Opcional para IA:

```text
AI_PROVIDER=auto
GEMINI_API_KEY=<chave>
GEMINI_IMAGE_MODEL=gemini-3-pro-image
AI_PREVIEW_MAX_PER_ORDER=5
AI_PREVIEW_RATE_WINDOW_HOURS=24
AI_PREVIEW_CACHE_ENABLED=true
AI_PREVIEW_CACHE_TTL_HOURS=24
```

Opcional para Llama/Ollama (texto apenas):

```text
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://<servico-ollama>:11434
OLLAMA_MODEL=llama3.2:3b
```

Opcional para WhatsApp:

```text
META_WHATSAPP_TOKEN=<token>
META_PHONE_NUMBER_ID=<phone-number-id>
META_WEBHOOK_VERIFY_TOKEN=<verify-token>
META_APP_SECRET=<app-secret>
META_API_VERSION=v21.0
```

## 3. Validacao automatica

Assim que a URL publica existir:

```bash
python scripts/smoke_railway.py https://<url-publica>
```

O teste valida:

- `/health`
- `/login`
- `/metrics`
- `/api/catalog`

Com credenciais do painel:

```bash
python scripts/smoke_railway.py https://<url-publica> --user admin --password '<senha>'
```

## 4. Teste funcional minimo

No painel:

1. Login com `ADMIN_USER` / `ADMIN_PASSWORD`.
2. Abrir catalogo e confirmar que existem modelos.
3. Criar cliente teste.
4. Criar pedido teste.
5. Gerar preview tecnico.
6. Aprovar pedido.
7. Baixar pacote de producao.
8. Conferir no Postgres se `orders`, `clients`, `order_revisions` e `audit_log` receberam linhas.

## 5. Bloqueios atuais

- Railway mostra aviso de assinatura pendente no workspace.
- Railway pode pausar deploys por incidente upstream.
- Arquivos gerados pelo app ainda ficam no disco do container; para producao real, definir volume Railway ou storage externo.
