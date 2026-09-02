# Pizza Box Agent — visão geral do projeto

**Última atualização:** 2026-09-01

## 1. O que é o projeto

O Pizza Box Agent é uma ferramenta de pré-venda e preparação de arte para fabricantes de
caixas de pizza. Ele recebe os dados de uma pizzaria pelo painel administrativo ou WhatsApp,
associa o pedido a um modelo de caixa, gera uma imagem para aprovação e prepara os arquivos que
seguem para o processo de produção gráfica.

O projeto busca reduzir o trabalho manual entre o primeiro contato comercial e a aprovação da
arte, mantendo cliente, pedido, revisões, arquivos e status em um único sistema.

Precificação e pagamento não fazem parte do escopo atual.

## 2. Para quem ele existe

- **Equipe comercial:** cadastra clientes e inicia pedidos.
- **Atendimento:** acompanha a conversa, envia previews e recebe aprovações ou ajustes.
- **Designer:** recebe os dados e o pacote de produção para finalizar o material gráfico.
- **Operação da fábrica:** acompanha pedidos aprovados, em produção e entregues.
- **Administrador:** configura catálogo, WhatsApp, acesso e acompanha indicadores operacionais.

## 3. Fluxo principal

```text
Contato do cliente
        |
        v
Cadastro ou identificação pelo telefone
        |
        v
Escolha do modelo e criação do pedido
        |
        v
Envio dos dados, logo e referências
        |
        v
Geração e envio do preview
        |
        +---- pedido de ajuste ----+
        |                          |
        v                          |
     aprovação <------------------+
        |
        v
Preparação do arquivo/pacote de produção
        |
        v
Produção e entrega
```

O ciclo de status persistido atualmente é:

```text
draft -> preview_sent -> revision -> approved -> production -> delivered
```

O pedido pode alternar entre preview e revisão até ser aprovado.

## 4. Canais de uso

### Painel web

Interface administrativa renderizada no servidor. Permite gerenciar clientes, catálogo e
pedidos, acompanhar o Kanban do funil operacional, gerar previews, aprovar trabalhos e acessar
configurações.

### API HTTP

Endpoints FastAPI usados pelo painel e por integrações. A API cobre autenticação, clientes,
catálogo, pedidos, arquivos, estatísticas e WhatsApp.

### WhatsApp

O webhook da Meta recebe mensagens, identifica o cliente pelo telefone e conduz a conversa. No
primeiro contato, o cliente é criado automaticamente. O fluxo pode apresentar o catálogo,
receber dados e imagens, criar o pedido, enviar o preview e interpretar aprovação ou pedido de
ajuste.

## 5. Componentes principais

| Área | Responsabilidade |
|---|---|
| `app/api/` | endpoints JSON da aplicação |
| `app/web/` | rotas e ações do painel administrativo |
| `app/templates/` | telas Jinja2 do painel |
| `app/services/` | regras de pedido, produção, logo, WhatsApp e controle de custo de IA |
| `app/db/` | modelos SQLAlchemy, sessões e repositórios |
| `app/psd/` | leitura, calibração, composição e renderização dos modelos gráficos |
| `app/ai/` | interpretação de mensagens, visão e geração do mockup por IA |
| `app/integrations/` | comunicação com serviços externos, principalmente a API da Meta |
| `app/print_specs/` | composição e especificações do caminho de arte para impressão |
| `gabaritos/` | modelos de caixa e arquivos de calibração |
| `storage/` | banco e arquivos gerados em tempo de execução |
| `alembic/` | migrações do banco de dados |
| `tests/` | testes automatizados |
| `scripts/` | catálogo, smoke test, backup e utilitários de preparação |

## 6. Arquitetura

O backend usa Python 3.11+, FastAPI e Jinja2. A persistência é feita com SQLAlchemy, usando
SQLite no desenvolvimento local e PostgreSQL em produção. O Alembic controla as migrações de
produção, enquanto a inicialização local mantém compatibilidade com o banco SQLite existente.

As regras de negócio ficam principalmente em serviços. As rotas recebem a requisição,
validam autenticação e dados, chamam serviços ou repositórios e retornam HTML ou JSON.

```text
Painel / WhatsApp / API
          |
          v
    FastAPI e rotas
          |
          v
 Serviços de negócio -----> Provedores de IA
          |                API da Meta
          v
 Repositórios SQLAlchemy
          |
          v
 SQLite ou PostgreSQL
```

## 7. Domínio atual

### Cliente

Guarda nome, telefone, Instagram, logo e datas de cadastro. O telefone é único e normalizado,
permitindo reconhecer o mesmo cliente entre painel, API e WhatsApp.

### Modelo de caixa

Representa um gabarito disponível no catálogo, com nome, dimensões, tipo de produto, campos
editáveis, calibração, thumbnail e estado ativo.

### Pedido

Liga um cliente a um modelo e mantém quantidade, dados editáveis, status, arquivos de preview e
produção e datas de atualização.

### Revisão

Registra cada versão do preview, sua origem, dados utilizados e feedback do cliente.

### Mensagem do WhatsApp

Registra o identificador único da mensagem recebida para impedir processamento duplicado e pode
associá-la ao pedido correspondente.

### Auditoria e configuração

O sistema mantém conta administrativa, configuração do WhatsApp e trilha de auditoria para
ações relevantes sobre pedidos.

## 8. Geração de arte

Existem dois resultados visualmente semelhantes, mas com finalidades diferentes:

| Resultado | Finalidade | Observação |
|---|---|---|
| preview técnico | conferir a composição do gabarito | deriva do modelo e da calibração |
| preview por IA | apresentar um mockup rápido ao cliente | é ilustrativo e possui custo por geração |
| arquivo/pacote de produção | continuar o trabalho gráfico após aprovação | não deve ser substituído pelo mockup de IA |

O caminho operacional recomendado para novos modelos usa arte plana calibrada. O caminho legado
edita PSD e gera saída CMYK, mas possui limitações para recursos complexos do Photoshop. A
arquitetura detalhada está em `docs/ARQUITETURA_OPERACIONAL.md`.

## 9. Dados e arquivos

O banco registra metadados e relacionamentos. Imagens, previews, PSDs e pacotes são armazenados
em diretórios de runtime e seus caminhos são associados aos pedidos.

Conteúdo típico:

- `storage/pizzabox.db`: banco SQLite local;
- `storage/logos/`: logos recebidas;
- `storage/preview/`: previews gerados;
- `storage/output/`: saídas de produção;
- `storage/thumbnails/`: miniaturas do catálogo;
- `temp/`: arquivos temporários.

Em produção, o banco recomendado é PostgreSQL. A persistência dos arquivos precisa ser
considerada na configuração da hospedagem, pois o sistema depende deles após a geração.

## 10. Segurança e operação

- o painel usa autenticação administrativa por sessão;
- endpoints administrativos exigem autenticação;
- webhooks do WhatsApp validam a assinatura configurada da Meta;
- segredos ficam em variáveis de ambiente ou configuração protegida, nunca na documentação;
- `/health` verifica processo e acesso ao banco;
- `/metrics` expõe métricas compatíveis com Prometheus;
- o projeto possui scripts de backup, smoke test e carga do catálogo;
- o deploy previsto usa Docker e pode executar migrações Alembic antes da inicialização.

## 11. Funcionalidades existentes

- cadastro e busca de clientes;
- registro automático do cliente no primeiro contato pelo WhatsApp;
- catálogo de modelos de caixa;
- criação e acompanhamento de pedidos;
- revisões e feedback sobre preview;
- preview técnico e mockup por IA;
- aprovação e preparação de saída de produção;
- envio e recebimento pelo WhatsApp;
- painel administrativo e Kanban por status;
- estatísticas operacionais básicas;
- auditoria, saúde, métricas e limpeza controlada de arquivos.

## 12. Evolução planejada: CRM

O cadastro atual identifica o cliente, mas ainda não constitui um CRM completo. A evolução
planejada adicionará perfil de relacionamento, histórico de interações, classificação automática
como VIP e Abandono, tarefas de reengajamento e métricas reais de conversão.

Essa evolução está especificada em `docs/SDD_CRM_E_FUNIL.md`. Até sua implementação, o
`/funil` deve ser entendido como um Kanban operacional de pedidos, não como um dashboard
histórico de conversão comercial.

## 13. Limites e dependências externas

- credenciais e configuração da Meta são necessárias para o WhatsApp real;
- o webhook requer uma URL pública com HTTPS;
- facas e gabaritos definitivos dependem da gráfica;
- fontes usadas nos modelos precisam estar instaladas no ambiente;
- gerações de IA dependem de provedor, chave, disponibilidade e orçamento;
- mockup de IA não é arquivo final de impressão;
- o caminho PSD não preserva todos os recursos avançados do Photoshop;
- arquivos de runtime precisam de armazenamento persistente e política de backup.

## 14. Onde começar

Para desenvolver ou revisar o projeto:

1. leia `README.md` para instalação e configuração;
2. consulte `app/main.py` para os pontos de entrada;
3. leia `app/services/order_service.py` para o ciclo principal do pedido;
4. consulte `app/services/whatsapp_service.py` para a conversa automatizada;
5. leia `app/db/models.py` e `app/db/repositories.py` para entender os dados;
6. use `docs/ARQUITETURA_OPERACIONAL.md` para decisões sobre produção gráfica;
7. use `docs/SDD_CRM_E_FUNIL.md` para planejar a evolução de CRM.
