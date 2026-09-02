# SDD — Gerenciamento de armazenamento

**Status:** implementado localmente
**Ultima atualizacao:** 2026-09-02
**Escopo:** dashboard de storage, alertas de capacidade e politica de retencao automatica
**Implementacao:** `app/services/storage_service.py`, `/api/storage`, dashboard e
`scripts/storage_maintenance.py`

## 1. Contexto

O Pizza Box Agent gera e recebe arquivos grandes durante o fluxo de pre-venda e producao:
gabaritos PSD, logos, referencias do cliente, previews JPG, PSDs finais em CMYK, pacotes de
producao, thumbnails, arquivos temporarios e backups do banco. Esses arquivos sao essenciais
para a operacao, mas podem crescer rapidamente e aumentar custo de storage, risco de falha em
deploy e dificuldade de localizar arquivos relevantes.

O sistema ja possui uma leitura inicial de uso de disco no dashboard e endpoints simples de
preview/execucao de limpeza. Este SDD define a evolucao necessaria para transformar essa base
em um modulo confiavel de monitoramento, alerta e retencao automatica.

## 2. Objetivo

Construir um painel de monitoramento de armazenamento, alertas de capacidade e rotinas de
limpeza configuraveis, preservando arquivos ativos e evitando exclusoes destrutivas sem
criterio explicito.

Resultados esperados:

- medir uso total de disco e uso por categoria de arquivo;
- exibir status operacional no dashboard;
- disparar alertas quando o uso atingir 80% e 90%;
- permitir simulacao de limpeza antes da execucao;
- executar limpeza automatica por politica configuravel;
- registrar auditoria das limpezas e alertas;
- entregar script de manutencao agendavel por cron ou job externo.

## 3. Estado atual verificado

O projeto ja possui parte da base necessaria:

- `app/config.py` define diretorios de runtime: `storage/output`, `storage/art_masters`,
  `storage/preview`, `storage/thumbnails`, `storage/logos`, `temp` e `gabaritos`;
- `app/templates/dashboard.html` ja mostra um card de espaco em disco;
- `app/api/stats.py` expoe `/api/stats` com uso total de disco e breakdown parcial;
- `app/api/stats.py` expoe `/api/cleanup/preview` e `/api/cleanup/execute`;
- `scripts/backup.sh` cria backup manual e mantem os ultimos 30 backups;
- `AuditLog` ja existe e pode registrar eventos de sistema com `order_id` nulo.

Lacunas antes da implementacao deste epico:

- thresholds de alerta nao sao configuraveis;
- alerta acima de 80% existe apenas como sinal visual simples;
- nao ha tratamento separado para 80% e 90%;
- nao ha cooldown de alerta para evitar repeticao excessiva;
- a limpeza atual nao possui politica de idade configuravel;
- a limpeza automatica por cron ainda nao existe;
- nao ha relatorio detalhado de candidatos a exclusao;
- nao ha allowlist centralizada de diretorios limpaveis;
- nao ha auditoria especifica de alerta e limpeza;
- dashboard e API duplicam parte da logica de calculo de disco.

## 4. Escopo funcional

### 4.1 Dashboard de storage

O dashboard deve exibir:

- percentual de disco usado;
- espaco total, usado e livre;
- status `ok`, `warning` ou `critical`;
- breakdown por categoria;
- top maiores diretorios ou arquivos sob gestao do sistema;
- ultima verificacao;
- ultimo alerta emitido;
- ultima limpeza executada;
- estimativa de espaco liberavel pela politica atual.

Categorias minimas:

| Categoria | Diretorio ou origem | Tratamento |
|---|---|---|
| Templates | `gabaritos/` | preservar |
| Previews | `storage/preview/` | limpavel por retencao |
| PSDs de saida | `storage/output/` | limpavel para pedidos entregues |
| Artes mestres | `storage/art_masters/` | preservar inicialmente |
| Logos | `storage/logos/` | preservar enquanto cliente/pedido existir |
| Thumbnails | `storage/thumbnails/` | regeneravel |
| Temporarios | `temp/` | limpavel por idade |
| Backups | `storage/backups/` | limpavel por quantidade/idade |
| Banco local | `storage/pizzabox.db` | preservar |

### 4.2 Alertas de capacidade

O sistema deve avaliar o percentual de uso de disco contra dois thresholds:

| Nivel | Threshold padrao | Acao |
|---|---:|---|
| `warning` | 80% | exibir alerta no painel e registrar evento |
| `critical` | 90% | exibir alerta critico, registrar evento e recomendar limpeza imediata |

Regras:

- thresholds devem ser configuraveis por variavel de ambiente;
- o status mais severo prevalece;
- alertas repetidos devem respeitar cooldown configuravel;
- alertas devem ser auditaveis;
- uma queda abaixo do threshold deve permitir novo alerta futuro quando o limite for cruzado
  novamente.

### 4.3 Politica de retencao automatica

A limpeza deve ser controlada por configuracao e sempre suportar modo `dry-run`.

Politicas iniciais propostas:

| Item | Regra padrao | Observacao |
|---|---:|---|
| Arquivos temporarios | apagar apos 24 horas | exceto `.gitkeep` |
| Previews de revisao | apagar apos 30 dias se pedido entregue | preservar pedido ativo |
| PSD RGB de saida | apagar apos 30 dias se pedido entregue | limpar campo no pedido |
| PSD CMYK final | apagar apos 30 dias se pedido entregue | opcao conservadora |
| Thumbnails | apagar apos 90 dias se regeneraveis | opcional |
| Backups | manter ultimos 30 | ja existe parcialmente |

Arquivos nunca apagados pela rotina automatica:

- arquivos dentro de `gabaritos/`;
- banco de dados;
- `.env` e arquivos de configuracao;
- arquivos de pedidos nao entregues;
- logos de clientes ainda vinculadas;
- paths fora dos diretorios permitidos;
- symlinks que apontem para fora do projeto.

### 4.4 Execucao manual

O painel deve permitir:

- simular limpeza usando a politica atual;
- listar quantidade de arquivos, bytes liberaveis e motivos;
- executar limpeza manual quando o usuario confirmar;
- exibir resultado com arquivos removidos, falhas e total liberado.

A execucao manual deve usar o mesmo servico da rotina automatica.

### 4.5 Execucao automatica

Criar script agendavel:

```bash
.venv/bin/python scripts/storage_maintenance.py --execute
```

Flags propostas:

```bash
--dry-run
--execute
--json
--retention-delivered-days 30
--retention-temp-hours 24
--max-backups 30
--fail-on-critical
```

Exemplo de cron local:

```cron
0 3 * * * cd /caminho/do/projeto && .venv/bin/python scripts/storage_maintenance.py --execute >> storage/logs/storage_maintenance.log 2>&1
```

Em Railway ou outro provedor, a mesma rotina deve rodar como scheduled job, sem depender de
request HTTP.

## 5. Arquitetura proposta

Criar um servico de dominio central:

```text
app/services/storage_service.py
```

Responsabilidades:

- calcular snapshot de disco;
- calcular breakdown por categoria;
- avaliar alertas;
- montar plano de limpeza;
- executar limpeza;
- validar paths permitidos;
- registrar resultados para auditoria.

O dashboard, a API e o script cron devem chamar esse servico. A regra de negocio nao deve ficar
espalhada em templates nem diretamente nos endpoints.

Fluxo proposto:

```text
dashboard/API/cron
      |
      v
storage_service
      |
      +--> filesystem
      +--> settings
      +--> database
      +--> audit_log
```

## 6. Configuracoes propostas

Adicionar em `Settings`:

| Variavel | Padrao | Uso |
|---|---:|---|
| `STORAGE_WARNING_THRESHOLD_PERCENT` | `80` | alerta de atencao |
| `STORAGE_CRITICAL_THRESHOLD_PERCENT` | `90` | alerta critico |
| `STORAGE_CLEANUP_ENABLED` | `false` | habilita rotina automatica |
| `STORAGE_CLEANUP_DRY_RUN` | `true` | impede exclusao real por padrao |
| `STORAGE_RETENTION_DELIVERED_DAYS` | `30` | idade minima para limpar pedidos entregues |
| `STORAGE_RETENTION_TEMP_HOURS` | `24` | idade minima para limpar temporarios |
| `STORAGE_BACKUP_MAX_FILES` | `30` | quantidade maxima de backups |
| `STORAGE_ALERT_COOLDOWN_HOURS` | `24` | janela minima entre alertas iguais |
| `STORAGE_MANAGED_PATHS` | padrao interno | allowlist opcional de diretorios |

## 7. APIs propostas

### `GET /api/storage`

Retorna snapshot completo:

```json
{
  "status": "warning",
  "percent_used": 82.4,
  "total_gb": 10.0,
  "used_gb": 8.2,
  "free_gb": 1.8,
  "thresholds": {
    "warning": 80,
    "critical": 90
  },
  "breakdown": [
    {"category": "previews", "path": "storage/preview", "size_mb": 120.5},
    {"category": "output", "path": "storage/output", "size_mb": 840.2}
  ],
  "cleanup_estimate": {
    "files": 42,
    "freed_mb": 512.8
  }
}
```

### `GET /api/storage/cleanup/preview`

Retorna plano detalhado sem excluir arquivos.

### `POST /api/storage/cleanup/execute`

Executa a limpeza conforme politica atual.

Requisitos:

- exigir autenticacao;
- nunca aceitar path arbitrario vindo do cliente;
- registrar auditoria;
- retornar falhas parciais.

## 8. Modelo de auditoria

Usar `AuditLog` existente com `order_id=None`.

Eventos propostos:

| Evento | Quando |
|---|---|
| `storage_alert_warning` | uso cruza o limite de 80% |
| `storage_alert_critical` | uso cruza o limite de 90% |
| `storage_cleanup_previewed` | usuario ou cron simulou limpeza |
| `storage_cleanup_executed` | limpeza removeu arquivos |
| `storage_cleanup_failed` | limpeza teve erro geral |

`details` deve conter:

- percentual de uso;
- thresholds usados;
- quantidade de arquivos candidatos/removidos;
- MB liberaveis/liberados;
- modo `dry_run`;
- politica de retencao usada;
- erros parciais, quando houver.

## 9. Regras de seguranca

A rotina de limpeza deve seguir estas regras tecnicas:

- resolver todos os paths com `Path.resolve()`;
- verificar se o arquivo esta dentro de um diretorio permitido;
- rejeitar symlink para fora do projeto;
- ignorar arquivos inexistentes no momento da exclusao;
- tratar erro por arquivo sem abortar o lote inteiro;
- nao apagar diretorios inteiros sem validar cada arquivo;
- manter operacao idempotente;
- executar primeiro em `dry-run` nos ambientes novos.

## 10. Plano de implementacao

### Fase 1 — Base de configuracao

- adicionar configuracoes de storage em `app/config.py`;
- criar constantes de categorias e paths gerenciados;
- garantir criacao de `storage/logs` e `storage/backups` quando necessario.

### Fase 2 — Servico de storage

- criar `app/services/storage_service.py`;
- mover calculo de disco de `app/api/stats.py` para o servico;
- implementar snapshot, breakdown e status;
- adicionar plano de limpeza em modo dry-run.

### Fase 3 — Alertas

- implementar avaliacao `ok`/`warning`/`critical`;
- registrar eventos no `AuditLog`;
- implementar cooldown;
- adicionar testes de thresholds 80% e 90%.

### Fase 4 — APIs e dashboard

- criar endpoints `/api/storage`, `/api/storage/cleanup/preview` e
  `/api/storage/cleanup/execute`;
- manter compatibilidade ou redirecionar os endpoints antigos de cleanup;
- atualizar dashboard para mostrar status, breakdown completo e ultima limpeza;
- adicionar botoes de simular e executar limpeza.

### Fase 5 — Script de manutencao

- criar `scripts/storage_maintenance.py`;
- suportar `--dry-run`, `--execute` e `--json`;
- integrar com `storage_service`;
- documentar cron local e scheduled job de producao.

### Fase 6 — Testes e validacao

- testar snapshot e breakdown;
- testar thresholds de 80% e 90%;
- testar cooldown de alerta;
- testar dry-run sem exclusao;
- testar exclusao apenas em paths permitidos;
- testar preservacao de pedidos ativos;
- testar limpeza de temporarios antigos;
- testar auditoria de limpeza;
- rodar suite completa.

## 11. Criterios de aceite

O epico sera considerado concluido quando:

- o painel mostrar monitoramento de disco com status e breakdown por categoria;
- alertas forem disparados em 80% e 90%;
- alertas forem registrados em auditoria e respeitarem cooldown;
- limpeza automatica configuravel estiver funcional;
- limpeza manual suportar preview antes de executar;
- script de manutencao puder ser agendado por cron ou scheduled job;
- arquivos ativos e paths fora da allowlist forem preservados;
- testes cobrirem thresholds, dry-run, execucao e preservacao de dados.

## 12. Entregaveis

Entregaveis tecnicos:

- `app/services/storage_service.py`;
- endpoints de storage e cleanup;
- dashboard de monitoramento atualizado;
- `scripts/storage_maintenance.py`;
- documentacao de agendamento;
- testes automatizados.

Arquivos implementados:

| Arquivo | Papel |
|---|---|
| `app/config.py` | configuracoes de thresholds, retencao, dry-run, backups e logs |
| `.env.example` | exemplo das variaveis de storage para deploy e cron |
| `app/services/storage_service.py` | regra central de snapshot, alerta, plano e execucao de limpeza |
| `app/api/stats.py` | endpoints `/api/storage`, `/api/storage/cleanup/*` e compatibilidade `/api/cleanup/*` |
| `app/web/views.py` | dashboard e partials HTMX usando o servico central |
| `app/templates/dashboard.html` | visual de status `ok`/`warning`/`critical`, breakdown e estimativa de limpeza |
| `scripts/storage_maintenance.py` | entrada agendavel por cron/scheduled job |
| `tests/test_stats_api.py` | cobertura de auth, thresholds, cooldown, dry-run/execucao e retencao |
| `tests/conftest.py` | isolamento de diretorios `backups` e `logs` nos testes |

Entregaveis operacionais:

- politica padrao de retencao;
- relatorio de simulacao de limpeza;
- registro de alertas;
- registro de limpezas executadas.

## 13. Riscos e decisoes pendentes

| Risco ou decisao | Recomendacao |
|---|---|
| Apagar PSD final de pedido entregue pode dificultar reimpressao | usar 30 dias como padrao e tornar configuravel |
| Railway pode ter storage efemero dependendo do volume configurado | validar volume persistente antes de confiar em arquivos locais |
| Backups locais podem nao bastar em producao | manter backup externo ou snapshot do Postgres |
| Alerta por email/WhatsApp ainda nao definido | primeira versao deve registrar no painel e auditoria |
| Gabaritos pesados podem dominar o storage | nao apagar automaticamente; tratar como decisao manual |
