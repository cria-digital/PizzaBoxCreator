# Arquitetura operacional do Pizza Box Agent

Este documento descreve o estado atual do app. O PDF de entrega tecnica em
`/Users/igorrangelkonvictus/Downloads/Pizza_Box_Status.pdf` foi usado como contexto historico,
mas varias lacunas citadas nele ja foram implementadas no codigo atual.

## Objetivo do sistema

O app automatiza a pre-venda de caixas personalizadas: coleta dados do cliente, gera preview de
aprovacao, registra revisoes/aprovacao e entrega ao designer um pacote para fechamento grafico.
Precificacao e pagamento seguem fora do escopo do produto.

## Fluxo principal

1. Cliente e modelo sao escolhidos pelo painel, API ou WhatsApp.
2. O pedido e criado como `draft`, com `created_by` preenchido quando ha usuario autenticado.
3. O preview pode seguir por tres caminhos:
   - `flat`: imagem plana leve + calibracao, caminho preferencial para modelos novos.
   - `psd`: motor legado com PhotoshopAPI, usado quando nao existe imagem plana.
   - `ai`: mockup pago de aprovacao, protegido por cache e limite por pedido.
4. Cada preview gera uma linha em `order_revisions` com `preview_source`.
5. Rejeicoes gravam feedback na revisao mais recente e devolvem o pedido para `revision`.
6. Aprovacao move o pedido para `production`, gera pacote ZIP para o designer e, no caminho PSD,
   tambem gera o PSD CMYK legado.
7. Criacao, aprovacao e rejeicao sao registradas em `audit_log`.

## Caminho recomendado para novos modelos

Use arte plana exportada do design original, por exemplo:

- `modelo_flat.png`
- `modelo_flat_kraft.png`
- `modelo_flat_premium.png`

Esses arquivos ficam em `gabaritos/`, ao lado do PSD ou do cadastro legado. A calibracao visual em
`/catalogo/{id}/calibrar` posiciona telefone, Instagram, frase e logo sobre a imagem. Esse caminho
tira o PSD pesado do caminho critico e evita perda de efeitos, fontes e smart objects.

O PSD ainda existe como fallback para compatibilidade e para modelos antigos.

## Pacote de producao

Ao aprovar, o sistema cria `storage/output/pedido_{id}_producao.zip` com:

- preview aprovado pelo cliente;
- logo do cliente;
- imagens planas da arte, quando existirem;
- `pedido_{id}_spec.json` com textos, tema, modelo e calibracao;
- `LEIA_ME.txt` para orientar o designer.

Esse pacote e o entregavel preferencial para a grafica/designer. O arquivo CMYK gerado pelo caminho
PSD continua disponivel apenas quando o pedido teve um `output_psd`.

## Banco e migracoes

Localmente, o padrao e SQLite em `storage/pizzabox.db`. Em producao, use PostgreSQL com Alembic:

```bash
alembic upgrade head
```

O `docker-compose.yml` ja executa a migracao antes de subir a aplicacao. Para SQLite existente, o
boot aplica migracoes aditivas pequenas para colunas novas, como `orders.created_by` e
`order_revisions.preview_source`.

## Deploy

O deploy de referencia usa:

- `Dockerfile` para a aplicacao FastAPI;
- `docker-compose.yml` com PostgreSQL 16, app e servico de backup;
- `scripts/backup.sh` para backup manual de SQLite ou PostgreSQL;
- `/metrics` em formato Prometheus;
- logs estruturados JSON.

Antes de expor publicamente:

- configurar `SECRET_KEY` e `ADMIN_PASSWORD` fortes;
- trocar `CORS_ORIGINS=*` por origens explicitas;
- ligar `SECURE_COOKIES=true` atras de HTTPS;
- instalar fontes usadas nos modelos;
- configurar credenciais Meta se o WhatsApp for ativado.

## Pendencias que nao sao resolvidas so com codigo

- Credenciais Meta / WhatsApp Business do cliente.
- Host publico HTTPS para webhook da Meta.
- Arquivos de faca reais da grafica.
- Homologacao grafica modelo a modelo, incluindo dimensao fisica, cor, registro e corte.

## Validacao atual

A validacao automatizada atual e:

```bash
python -m pytest -q
```

Estado verificado: 239 testes passando.
