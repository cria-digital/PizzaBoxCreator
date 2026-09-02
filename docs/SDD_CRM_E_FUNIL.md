# SDD — CRM, classificação e funil de conversão

**Status:** proposta para planejamento
**Última atualização:** 2026-09-01
**Escopo:** módulo de CRM, classificação automática, reengajamento e dashboard de funil
**Implementação:** ainda não iniciada

## 1. Contexto

O Pizza Box Agent já registra clientes, pedidos e mensagens recebidas pelo WhatsApp. Porém,
esses dados ainda são usados principalmente para operar pedidos. Não existe uma camada de CRM
que consolide o relacionamento, classifique contatos, identifique abandono ou acompanhe as
conversões entre as etapas comerciais.

Esta especificação define a evolução necessária para transformar os dados operacionais atuais
em uma visão de relacionamento e conversão, sem substituir o fluxo de pedidos existente.

## 2. Objetivo

Modelar entidades de CRM e automatizar a classificação de clientes e o reengajamento, com um
dashboard que permita acompanhar o funil comercial e agir sobre contatos que precisam de
atenção.

Os resultados esperados são:

- registrar automaticamente todo contato identificável;
- manter um perfil de CRM por cliente;
- classificar clientes, incluindo VIP e Abandono;
- registrar o histórico das mudanças de classificação;
- criar tarefas de reengajamento sem duplicidade;
- medir volume, avanço, abandono e conversão do funil;
- permitir auditoria das decisões automáticas.

## 3. Estado atual verificado

O projeto já possui parte da base necessária:

- `clients` registra nome, telefone, Instagram e logo;
- o telefone é normalizado e funciona como identificador único do cliente;
- `POST /api/clients` cria ou atualiza um cliente;
- o primeiro contato recebido pelo WhatsApp cria o cliente automaticamente;
- `orders` registra o ciclo operacional do pedido;
- os status atuais são `draft`, `preview_sent`, `revision`, `approved`, `production` e
  `delivered`;
- `whatsapp_messages` evita o reprocessamento da mesma mensagem recebida;
- `/api/stats` expõe totais operacionais e pedidos por status;
- `/funil` é hoje um Kanban de pedidos, e não um funil de conversão de CRM.

Lacunas atuais:

- não há perfil de CRM nem classificação de cliente;
- não há histórico consolidado de interações comerciais;
- não há regras de abandono, risco ou VIP;
- não há fila de reengajamento;
- não há métricas de passagem e conversão entre etapas;
- mudanças de status não preservam um histórico completo de transições, o que limita métricas
  históricas precisas.

## 4. Escopo funcional

### 4.1 Registro automático de contatos

Um cliente deve existir antes de qualquer dado de CRM ser registrado. A criação deve continuar
usando o telefone normalizado como chave natural.

O registro automático deve ocorrer quando:

- uma mensagem válida chega pelo WhatsApp e o telefone ainda não existe;
- um cliente é cadastrado pelo painel;
- um cliente é criado ou atualizado pela API;
- um pedido é criado por um fluxo que ainda não possua perfil de CRM.

Após a criação do cliente, o sistema deve criar seu perfil de CRM de forma idempotente. Repetir
o mesmo evento não pode gerar clientes ou perfis duplicados.

### 4.2 Perfil e classificação

Cada cliente deve possuir exatamente um perfil de CRM com:

- classificação atual;
- etapa atual do ciclo comercial;
- pontuação opcional;
- datas da última interação, último pedido e última classificação;
- data prevista para reengajamento;
- indicador de reengajamento pausado;
- motivo legível e dados usados na última classificação.

Classificações propostas:

| Classificação | Significado |
|---|---|
| `new` | contato registrado, ainda sem pedido |
| `active` | contato com pedido em andamento ou atividade recente |
| `vip` | cliente que atingiu o critério comercial de recorrência ou volume |
| `at_risk` | cliente parado em uma etapa relevante, mas ainda antes do abandono |
| `abandoned` | cliente com pedido ou negociação sem avanço além do limite definido |
| `inactive` | cliente sem pedido ou interação por um período prolongado |

A classificação representa uma prioridade de relacionamento. A etapa do funil deve ser mantida
em campo separado, pois um cliente VIP também pode ter um pedido em produção, por exemplo.

### 4.3 Etapas do funil

Etapas propostas para o CRM:

| Etapa | Entrada mínima |
|---|---|
| `lead` | contato criado |
| `qualified` | cliente escolheu modelo ou informou intenção de compra |
| `order_created` | pedido criado |
| `preview_sent` | preview enviado |
| `revision` | cliente solicitou ajuste |
| `approved` | cliente aprovou a arte |
| `production` | pedido entrou em produção |
| `delivered` | pedido entregue |

As etapas são progressivas para cálculo de conversão, mas uma revisão pode gerar ciclos entre
`preview_sent` e `revision`. Esses ciclos devem ser registrados no histórico sem inflar o número
de clientes únicos que avançaram no funil.

### 4.4 Interações

O CRM deve registrar eventos relevantes, no mínimo:

- contato criado;
- mensagem recebida;
- catálogo enviado;
- modelo selecionado;
- pedido criado;
- preview enviado;
- revisão solicitada;
- pedido aprovado;
- entrada em produção;
- pedido entregue;
- tarefa de reengajamento criada;
- reengajamento enviado, ignorado ou com falha.

Cada interação deve guardar cliente, pedido opcional, canal, direção, tipo, instante e metadados
estruturados. Conteúdo sensível de mensagens não deve ser copiado sem necessidade.

### 4.5 Reengajamento

Ao classificar um cliente como `at_risk`, `abandoned` ou `inactive`, o sistema deve poder criar
uma tarefa de reengajamento.

Requisitos:

- somente uma tarefa pendente por cliente, motivo e pedido;
- tarefa com data de agendamento, status e tentativas;
- opção de pausar reengajamento no perfil;
- status `pending`, `sent`, `skipped` e `failed`;
- registro da execução como interação;
- envio automático pelo WhatsApp somente após decisão de produto e validação de consentimento,
  janela de atendimento e template aprovado pela Meta.

A primeira versão recomendada cria tarefas para ação humana no painel. O envio automático deve
ser uma evolução posterior, protegida por configuração.

## 5. Regras de classificação

As regras devem ser centralizadas em serviço de domínio, configuráveis e executadas na ordem de
prioridade abaixo. Os valores entre colchetes precisam de decisão do negócio.

| Prioridade | Classificação | Regra inicial proposta |
|---:|---|---|
| 1 | `vip` | pelo menos `[N]` pedidos entregues ou `[Q]` caixas nos últimos `[P]` dias |
| 2 | `abandoned` | pedido em `draft`, `preview_sent` ou `revision` sem avanço há `[Z]` dias |
| 3 | `at_risk` | pedido em `preview_sent` ou `revision` sem resposta há `[Y]` dias, com `Y < Z` |
| 4 | `active` | pedido aberto ou entrega/interação dentro de `[A]` dias |
| 5 | `inactive` | nenhuma interação ou pedido dentro de `[W]` dias |
| 6 | `new` | cliente sem pedido e fora das condições anteriores |

Regras técnicas:

- a classificação deve produzir sempre o mesmo resultado para os mesmos dados e parâmetros;
- toda mudança deve gerar um evento de histórico com classificação anterior, nova, motivo e
  versão da regra;
- uma execução sem mudança deve apenas atualizar a data de avaliação, sem criar histórico
  duplicado;
- classificação manual, se adicionada, deve informar autor e validade da substituição;
- o relógio usado nas regras deve ser injetável para permitir testes determinísticos.

## 6. Gatilhos de domínio

Os gatilhos devem ser implementados na aplicação, após a persistência dos eventos de negócio,
e não como triggers SQL. Isso mantém as regras testáveis e compatíveis com SQLite e PostgreSQL.

| Evento | Ação de CRM |
|---|---|
| cliente criado ou atualizado | garantir perfil e reclassificar |
| mensagem recebida | registrar interação, atualizar último contato e reclassificar |
| pedido criado | registrar etapa `order_created` e reclassificar |
| status do pedido alterado | registrar transição, atualizar etapa e reclassificar |
| preview enviado | registrar etapa e programar avaliação de risco |
| revisão solicitada | registrar etapa e programar avaliação de risco |
| pedido aprovado | cancelar reengajamentos ligados ao abandono do pedido |
| pedido entregue | atualizar histórico de compra e reclassificar |
| rotina periódica | avaliar contatos cujo prazo de classificação venceu |

A atualização do pedido e o registro do respectivo evento de CRM devem ocorrer na mesma
transação sempre que fizerem parte da mesma operação.

## 7. Modelo de dados proposto

### `crm_profiles`

- `id`;
- `client_id`, único e obrigatório;
- `classification`;
- `lifecycle_stage`;
- `score`;
- `last_contact_at`;
- `last_order_at`;
- `last_classified_at`;
- `next_reengagement_at`;
- `reengagement_paused`;
- `classification_reason`;
- `classification_data` em JSON;
- `rule_version`;
- `created_at` e `updated_at`.

### `crm_interactions`

- `id`;
- `client_id`;
- `order_id`, opcional;
- `channel`: `whatsapp`, `web`, `api` ou `system`;
- `direction`: `inbound`, `outbound` ou `internal`;
- `event_type`;
- `payload` em JSON, limitado a metadados necessários;
- `occurred_at` e `created_at`;
- `idempotency_key`, opcional e única quando preenchida.

### `crm_classification_events`

- `id`;
- `client_id`;
- `previous_classification`;
- `new_classification`;
- `reason`;
- `evidence` em JSON;
- `rule_version`;
- `created_at`.

### `crm_reengagement_tasks`

- `id`;
- `client_id`;
- `order_id`, opcional;
- `reason`;
- `status`;
- `scheduled_for`;
- `attempt_count`;
- `sent_at`;
- `last_error`;
- `created_at` e `updated_at`.

### `order_status_events`

Tabela recomendada para métricas históricas confiáveis:

- `id`;
- `order_id`;
- `from_status`, opcional para a criação;
- `to_status`;
- `source`;
- `actor`, opcional;
- `created_at`.

Índices devem cobrir classificação, etapa, datas de avaliação, tarefas pendentes e todas as
chaves estrangeiras. A migração deve ser criada no Alembic e a inicialização local do SQLite
deve continuar compatível com a estratégia adotada pelo projeto.

## 8. Serviços e integrações

Estrutura proposta:

- `app/services/crm_service.py`: perfil, interação, classificação e transição de etapa;
- `app/services/reengagement_service.py`: criação, deduplicação e execução de tarefas;
- `app/api/crm.py`: consultas e comandos do módulo;
- métodos de repositório específicos em `app/db/repositories.py`, mantendo o padrão atual;
- integração pontual nos fluxos de clientes, pedidos e WhatsApp.

O serviço de classificação não deve enviar mensagens. Ele decide a classificação e cria uma
intenção de reengajamento; outro serviço executa essa intenção.

## 9. API proposta

| Método e rota | Finalidade |
|---|---|
| `GET /api/crm/contacts` | listar e filtrar contatos, classificação e etapa |
| `GET /api/crm/contacts/{client_id}` | obter perfil, pedidos, interações e histórico |
| `GET /api/crm/metrics` | obter métricas agregadas por período |
| `POST /api/crm/reclassify` | solicitar reclassificação em lote, restrita ao administrador |
| `GET /api/crm/reengagement` | listar tarefas de reengajamento |
| `POST /api/crm/reengagement/{task_id}/send` | executar uma tarefa pendente |
| `POST /api/crm/reengagement/{task_id}/skip` | ignorar uma tarefa com justificativa |

Filtros mínimos: período, classificação, etapa, origem, responsável e status da tarefa. Listas
devem ser paginadas antes de uso em produção com alto volume.

## 10. Dashboard de funil

O dashboard deve ser uma visão de CRM separada do Kanban operacional ou uma aba claramente
identificada dentro de `/funil`.

Métricas mínimas:

- total de contatos e novos contatos no período;
- contatos por classificação;
- clientes únicos por etapa do funil;
- conversão `lead → pedido`;
- conversão `pedido → preview`;
- conversão `preview → aprovado`;
- conversão `aprovado → entregue`;
- tempo mediano entre etapas;
- quantidade e taxa de abandono;
- clientes VIP;
- tarefas de reengajamento pendentes, enviadas e com falha.

Regras de cálculo:

- o período deve usar datas explícitas e exibir o fuso horário aplicado;
- conversão é calculada por clientes ou pedidos únicos, conforme o indicador, e essa unidade
  deve aparecer no rótulo;
- revisões repetidas não contam como novas conversões;
- etapas posteriores contam como passagem pelas etapas anteriores apenas se essa inferência for
  explicitamente adotada; o histórico real é preferível;
- quando o denominador for zero, a taxa deve ser exibida como não aplicável, não como infinito.

O painel deve permitir abrir a lista que originou cada indicador, tornando as métricas
acionáveis.

## 11. Critérios de aceite

### CA-01 — Registro automático pelo WhatsApp

**Dado** um telefone que ainda não existe
**Quando** uma mensagem válida for recebida
**Então** um cliente e um único perfil de CRM devem ser criados
**E** a interação deve ser registrada
**E** entregas repetidas da mesma mensagem não devem duplicar registros.

### CA-02 — Registro por painel ou API

**Dado** um cliente criado ou atualizado pelo painel ou pela API
**Quando** a operação for confirmada
**Então** o perfil de CRM deve existir
**E** o telefone normalizado deve continuar único.

### CA-03 — Classificação VIP

**Dado** um cliente que alcançou o limite VIP configurado
**Quando** um pedido for entregue ou a rotina de classificação executar
**Então** o cliente deve ser classificado como `vip`
**E** a justificativa e as evidências devem ser registradas no histórico.

### CA-04 — Classificação de abandono

**Dado** um pedido em uma etapa monitorada sem avanço além do prazo configurado
**Quando** a rotina de classificação executar
**Então** o cliente deve ser classificado como `abandoned`
**E** uma única tarefa pendente de reengajamento deve ser criada.

### CA-05 — Recuperação do abandono

**Dado** um cliente classificado como `abandoned`
**Quando** ele responder ou o pedido avançar
**Então** o cliente deve ser reclassificado
**E** tarefas pendentes incompatíveis devem ser canceladas ou ignoradas com motivo.

### CA-06 — Dashboard

**Dado** um conjunto conhecido de contatos, pedidos e transições
**Quando** o período for consultado
**Então** totais, etapas e taxas devem corresponder ao conjunto de teste
**E** revisões repetidas não devem inflar as conversões.

## 12. Requisitos não funcionais

- **Idempotência:** webhooks e rotinas repetidas não criam duplicidade.
- **Auditabilidade:** toda mudança automática de classificação informa regra e evidência.
- **Compatibilidade:** SQLite no desenvolvimento local e PostgreSQL em produção.
- **Segurança:** endpoints protegidos pela autenticação administrativa existente.
- **Privacidade:** armazenar somente dados necessários e oferecer pausa de reengajamento.
- **Desempenho:** consultas do dashboard agregadas no banco e apoiadas por índices.
- **Observabilidade:** registrar contagem de classificações, tarefas criadas, envios e falhas.
- **Testabilidade:** relógio e parâmetros das regras injetáveis; integrações externas simuladas.

## 13. Fora do escopo inicial

- CRM multiempresa;
- integração com CRM externo;
- campanhas em massa;
- segmentação por valor financeiro enquanto pedidos não possuírem preço;
- envio automático irrestrito de WhatsApp;
- modelos preditivos ou classificação por IA;
- substituição do Kanban operacional de pedidos.

## 14. Plano de ação

1. Aprovar os parâmetros de VIP, risco, abandono, inatividade e consentimento.
2. Criar enums, tabelas, índices e migração Alembic.
3. Implementar repositórios e o serviço determinístico de CRM.
4. Integrar o registro de eventos aos fluxos de cliente, WhatsApp e pedido.
5. Criar rotina segura de reclassificação e geração de tarefas.
6. Implementar API de contatos, métricas e reengajamento.
7. Construir a visão de CRM e o dashboard de funil.
8. Adicionar testes unitários, de integração, API e interface.
9. Validar migração em SQLite e PostgreSQL, carga das métricas e fluxo ponta a ponta.
10. Liberar primeiro o reengajamento assistido; avaliar automação após dados reais.

## 15. Decisões pendentes

Estas decisões devem ser respondidas antes da implementação das regras:

1. VIP será definido por quantidade de pedidos entregues, número de caixas, valor financeiro ou
   marcação manual?
2. Quantos dias sem resposta definem `at_risk`, `abandoned` e `inactive`?
3. A primeira versão apenas cria tarefas no painel ou também envia mensagens automaticamente?
4. Como será registrado o consentimento ou a recusa de mensagens de reengajamento?
5. O funil será medido principalmente por cliente único ou por pedido?
6. Uma classificação manual pode prevalecer sobre a automática? Por quanto tempo?

## 16. Definição de pronto

O módulo só deve ser considerado concluído quando:

- todos os critérios de aceite estiverem automatizados em testes;
- migrações funcionarem nos dois bancos suportados;
- registros antigos puderem receber perfil por rotina idempotente de backfill;
- o dashboard tiver dados rastreáveis até os registros de origem;
- tarefas de reengajamento não forem duplicadas;
- documentação de operação e configuração estiver atualizada;
- não houver regressão no cadastro de clientes, fluxo de pedidos ou WhatsApp.
