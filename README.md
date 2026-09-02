# PizzaBoxCreator
Monorepo do Pizza Box Creator.

## Estrutura

| Caminho | Responsabilidade |
|---|---|
| `/` | Frontend React/Vite criado a partir do Figma Make |
| `/backend` | Backend FastAPI do Pizza Box Agent, com API, painel legado, motor PSD e pipeline de arte |

## Contrato front/back

O frontend usa `VITE_API_BASE_URL` e chama estes endpoints do backend:

| Metodo | Endpoint |
|---|---|
| `POST` | `/api/auth/login` |
| `GET` | `/api/auth/me` |
| `POST` | `/api/auth/logout` |
| `GET` | `/api/clients` |
| `POST` | `/api/clients` |
| `PATCH` | `/api/clients/{id}` |
| `DELETE` | `/api/clients/{id}` |
| `GET` | `/api/orders` |
| `POST` | `/api/orders` |
| `GET` | `/api/catalog` |

Essas rotas são implementadas em `backend/app/api/`. As rotas HTML do backend, como `/login` e `/teste/ia-caixa`, continuam existindo para o painel legado e para o piloto de arte por IA.

## Railway

Use dois serviços Railway apontando para este mesmo repo GitHub:

| Servico | Root directory | Config | Variaveis principais |
|---|---|---|---|
| Frontend | `/` | `railway.json` | `VITE_API_BASE_URL=https://<backend-service>.up.railway.app` |
| Backend | `/backend` | `backend/railway.json` | `DATABASE_URL`, `ADMIN_PASSWORD`, `SECRET_KEY`, `SECURE_COOKIES=true`, `CORS_ORIGINS=https://<frontend-domain>` |

O backend executa `alembic upgrade head`, `python scripts/seed_catalog.py` e depois sobe `uvicorn`.

## Desenvolvimento local

Frontend:

```bash
pnpm install
pnpm dev
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gemini]"
cp .env.example .env
python scripts/seed_catalog.py
python -m uvicorn app.main:app --reload
```

Depois configure no frontend:

```bash
VITE_API_BASE_URL=http://localhost:8000
```
