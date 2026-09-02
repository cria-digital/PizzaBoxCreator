import { useEffect, useMemo, useState } from "react"
import {
  backendApi,
  type CrmClassification,
  type CrmContact,
  type CrmMetrics,
  type CrmReengagement,
  type CrmStage,
} from "../api/backend"
import { PageHeader } from "../components/PageHeader"
import { Icon } from "../components/ui/Icon"
import {
  Avatar,
  Badge,
  Button,
  Card,
  cx,
  type Tone,
} from "../components/ui/primitives"

const classifications: { value: CrmClassification | "all" label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "new", label: "Novos" },
  { value: "active", label: "Ativos" },
  { value: "vip", label: "VIP" },
  { value: "at_risk", label: "Em risco" },
  { value: "abandoned", label: "Abandonados" },
  { value: "inactive", label: "Inativos" },
]

const classificationMeta: Record<CrmClassification, {
  label: string
  tone: Tone
}> = {
  new: { label: "Novo", tone: "sauce" },
  active: { label: "Ativo", tone: "basil" },
  vip: { label: "VIP", tone: "cheese" },
  at_risk: { label: "Em risco", tone: "cheese" },
  abandoned: { label: "Abandonado", tone: "neutral" },
  inactive: { label: "Inativo", tone: "ink" },
}

const stages: { value: CrmStage label: string }[] = [
  { value: "lead", label: "Lead" },
  { value: "qualified", label: "Qualificado" },
  { value: "order_created", label: "Pedido" },
  { value: "preview_sent", label: "Preview" },
  { value: "revision", label: "Ajustes" },
  { value: "approved", label: "Aprovado" },
  { value: "production", label: "Produção" },
  { value: "delivered", label: "Entregue" },
]

const emptyMetrics: CrmMetrics = {
  contacts_total: 0,
  new_contacts: 0,
  by_classification: {
    new: 0,
    active: 0,
    vip: 0,
    at_risk: 0,
    abandoned: 0,
    inactive: 0,
  },
  by_stage: {
    lead: 0,
    qualified: 0,
    order_created: 0,
    preview_sent: 0,
    revision: 0,
    approved: 0,
    production: 0,
    delivered: 0,
  },
  stage_clients: {
    lead: 0,
    qualified: 0,
    order_created: 0,
    preview_sent: 0,
    revision: 0,
    approved: 0,
    production: 0,
    delivered: 0,
  },
  conversions: {
    lead_to_order: null,
    order_to_preview: null,
    preview_to_approved: null,
    approved_to_delivered: null,
  },
  abandoned_count: 0,
  abandoned_rate: null,
  vip_count: 0,
  reengagement: {},
}

function relativeDate(value?: string | null) {
  if (!value) return "Sem contato"
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) return "Sem contato"
  const days = Math.max(0, Math.floor((Date.now() - timestamp) / 86400000))
  if (days === 0) return "Hoje"
  if (days === 1) return "Ontem"
  return `${days} dias`
}

function percent(value: number | null) {
  return value === null ? "—" : `${Math.round(value * 100)}%`
}

export function FunilCrm() {
  const [contacts, setContacts] = useState<CrmContact[]>([])
  const [metrics, setMetrics] = useState<CrmMetrics>(emptyMetrics)
  const [tasks, setTasks] = useState<CrmReengagement[]>([])
  const [classification, setClassification] =
    useState<CrmClassification | "all">("all")
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState("")

  async function load() {
    setLoading(true)
    setError("")
    try {
      const data = await backendApi.loadCrm()
      setContacts(data.contacts)
      setMetrics(data.metrics)
      setTasks(data.tasks)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Falha ao carregar o CRM",
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const filteredContacts = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return contacts.filter((contact) => {
      const matchesClass =
        classification === "all" || contact.classification === classification
      const matchesQuery =
        !normalized ||
        contact.client.name.toLowerCase().includes(normalized) ||
        contact.client.phone.includes(normalized)
      return matchesClass && matchesQuery
    })
  }, [classification, contacts, query])

  async function reclassify() {
    setWorking(true)
    setError("")
    try {
      await backendApi.reclassifyCrm()
      await load()
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Falha ao reclassificar contatos",
      )
    } finally {
      setWorking(false)
    }
  }

  async function updateTask(taskId: number, action: "send" | "skip") {
    setWorking(true)
    setError("")
    try {
      if (action === "send") await backendApi.markReengagementSent(taskId)
      else await backendApi.skipReengagement(taskId)
      await load()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Falha ao atualizar a tarefa",
      )
    } finally {
      setWorking(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Funil CRM"
        subtitle="Acompanhe conversão, classificação dos contatos e oportunidades de reengajamento."
        actions={
          <Button
            variant="outline"
            onClick={reclassify}
            disabled={working || loading}
          >
            <Icon name="sparkles" size={16} />{" "}
            {working ? "Atualizando..." : "Reclassificar"}
          </Button>
        }
      />

      {error && (
        <p className="mb-5 rounded-xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm font-medium text-primary">
          {error}
        </p>
      )}

      <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Contatos", metrics.contacts_total, "Base CRM"],
          ["Clientes VIP", metrics.vip_count, "Maior valor"],
          [
            "Abandonados",
            metrics.abandoned_count,
            percent(metrics.abandoned_rate),
          ],
          ["Reengajamentos", metrics.reengagement.pending ?? 0, "Pendentes"],
        ].map(([label, value, note]) => (
          <Card key={String(label)} className="p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {label}
            </p>
            <div className="mt-3 flex items-end justify-between gap-3">
              <strong className="font-display text-4xl font-semibold text-foreground">
                {value}
              </strong>
              <span className="pb-1 text-xs text-muted-foreground">{note}</span>
            </div>
          </Card>
        ))}
      </div>

      <section className="mb-7 border-y border-border py-6">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-semibold">
              Jornada comercial
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Clientes únicos que alcançaram cada etapa.
            </p>
          </div>
          <Badge tone="basil" dot>
            Atualizado
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {stages.map((stage, index) => {
            const count = metrics.stage_clients[stage.value] ?? 0
            const base = Math.max(metrics.contacts_total, 1)
            return (
              <div
                key={stage.value}
                className="min-w-0 border-l-2 border-border px-3 first:border-primary"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-medium text-muted-foreground">
                    {stage.label}
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {index + 1}
                  </span>
                </div>
                <p className="mt-2 font-display text-2xl font-semibold">
                  {count}
                </p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.max(4, (count / base) * 100)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Lead → pedido", metrics.conversions.lead_to_order],
            ["Pedido → preview", metrics.conversions.order_to_preview],
            ["Preview → aprovação", metrics.conversions.preview_to_approved],
            ["Aprovação → entrega", metrics.conversions.approved_to_delivered],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="flex items-center justify-between border-t border-border pt-3 text-sm"
            >
              <span className="text-muted-foreground">{label}</span>
              <strong>{percent(value as number | null)}</strong>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-w-0">
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {classifications.map((item) => (
                <button
                  key={item.value}
                  onClick={() => setClassification(item.value)}
                  className={cx(
                    "rounded-full border px-3 py-1.5 text-xs font-medium",
                    classification === item.value
                      ? "border-ink bg-ink text-primary-foreground"
                      : "border-border bg-card text-secondary-foreground",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <label className="relative min-w-0 lg:w-64">
              <Icon
                name="search"
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar contato"
                className="h-9 w-full rounded-full border border-border bg-card pl-9 pr-3 text-sm outline-none focus:border-primary"
              />
            </label>
          </div>

          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="px-5 py-4 font-medium">Contato</th>
                    <th className="px-4 py-4 font-medium">Classificação</th>
                    <th className="px-4 py-4 font-medium">Etapa</th>
                    <th className="px-5 py-4 text-right font-medium">
                      Último contato
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredContacts.map((contact) => {
                    const meta = classificationMeta[contact.classification]
                    const stage =
                      stages.find(
                        (item) => item.value === contact.lifecycle_stage,
                      )?.label ?? contact.lifecycle_stage
                    return (
                      <tr
                        key={contact.id}
                        className="border-b border-border/60 last:border-0 hover:bg-secondary/40"
                      >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <Avatar name={contact.client.name} size={36} />
                            <div>
                              <p className="font-medium text-foreground">
                                {contact.client.name}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {contact.client.phone}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <Badge tone={meta.tone} dot>
                            {meta.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-4 text-secondary-foreground">
                          {stage}
                        </td>
                        <td className="px-5 py-4 text-right text-muted-foreground">
                          {relativeDate(contact.last_contact_at)}
                        </td>
                      </tr>
                    )
                  })}
                  {!loading && filteredContacts.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-5 py-12 text-center text-muted-foreground"
                      >
                        Nenhum contato encontrado.
                      </td>
                    </tr>
                  )}
                  {loading && (
                    <tr>
                      <td
                        colSpan={4}
                        className="px-5 py-12 text-center text-muted-foreground"
                      >
                        Carregando CRM...
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </section>

        <aside>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-xl font-semibold">
                Reengajamento
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Ações assistidas pendentes.
              </p>
            </div>
            <Badge tone="sauce">{tasks.length}</Badge>
          </div>
          <div className="space-y-3">
            {tasks.map((task) => (
              <Card key={task.id} className="p-4">
                <div className="flex items-start gap-3">
                  <Avatar name={task.client_name} size={34} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">
                      {task.client_name}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {task.client_phone}
                    </p>
                    <p className="mt-3 text-xs leading-relaxed text-secondary-foreground">
                      {task.reason.replaceAll("_", " ")}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2 border-t border-border pt-3">
                  <Button
                    className="flex-1 px-3 py-2 text-xs"
                    onClick={() => updateTask(task.id, "send")}
                    disabled={working}
                  >
                    <Icon name="chat" size={14} /> Marcar enviado
                  </Button>
                  <button
                    title="Ignorar tarefa"
                    aria-label="Ignorar tarefa"
                    onClick={() => updateTask(task.id, "skip")}
                    disabled={working}
                    className="grid size-9 shrink-0 place-items-center rounded-full border border-border text-muted-foreground hover:border-primary/50 hover:text-primary disabled:opacity-50"
                  >
                    <Icon name="plus" size={15} className="rotate-45" />
                  </button>
                </div>
              </Card>
            ))}
            {!loading && tasks.length === 0 && (
              <div className="border-t border-border py-8 text-center text-sm text-muted-foreground">
                Nenhuma ação pendente.
              </div>
            )}
          </div>
        </aside>
      </div>
    </>
  )
}
