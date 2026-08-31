import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { NewOrderModal } from "../components/NewOrderModal";
import { Icon, type IconName } from "../components/ui/Icon";
import {
  Badge,
  Button,
  Card,
  Gauge,
  SectionTitle,
  cx,
} from "../components/ui/primitives";
import { WEEK, stageTone, type Client, type Order } from "../data";
import { useAppStore } from "../store/AppStore";

/* ---------- stat cards ---------- */
type Stat = { label: string; value: string; delta: string; icon: IconName; highlight?: boolean };

function StatCard({ s }: { s: Stat }) {
  return (
    <Card
      className={cx(
        "relative overflow-hidden",
        s.highlight && "border-transparent bg-primary text-primary-foreground",
      )}
    >
      {s.highlight && (
        <div className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full bg-white/10 blur-2xl" />
      )}
      <div className="relative flex items-start justify-between">
        <span
          className={cx(
            "text-sm font-medium",
            s.highlight ? "text-primary-foreground/80" : "text-muted-foreground",
          )}
        >
          {s.label}
        </span>
        <span
          className={cx(
            "grid size-8 place-items-center rounded-full",
            s.highlight ? "bg-white/15 text-primary-foreground" : "bg-secondary text-secondary-foreground",
          )}
        >
          <Icon name={s.icon} size={16} />
        </span>
      </div>
      <div className="relative mt-6 font-display text-5xl font-semibold leading-none tracking-tight">
        {s.value}
      </div>
      <p
        className={cx(
          "relative mt-3 text-xs",
          s.highlight ? "text-primary-foreground/75" : "text-muted-foreground",
        )}
      >
        {s.delta}
      </p>
    </Card>
  );
}

/* ---------- render throughput chart ---------- */
function ThroughputChart() {
  const max = Math.max(...WEEK.map((w) => w.value));
  const peak = WEEK.reduce((a, b) => (b.value > a.value ? b : a));
  return (
    <Card>
      <SectionTitle
        action={
          <Badge tone="sauce" dot>
            Renderizações
          </Badge>
        }
      >
        Produção da semana
      </SectionTitle>
      <div className="flex h-52 items-end justify-between gap-3">
        {WEEK.map((w, i) => {
          const h = (w.value / max) * 100;
          const isPeak = w === peak;
          return (
            <div key={i} className="flex h-full flex-1 flex-col items-center justify-end gap-3">
              <div className="relative flex h-full w-full items-end justify-center">
                {isPeak && (
                  <span className="absolute -top-1 rounded-full bg-ink px-2 py-0.5 font-mono text-[10px] text-primary-foreground">
                    {w.value}
                  </span>
                )}
                <div
                  className={cx(
                    "w-full max-w-[38px] rounded-full transition-all duration-700",
                    isPeak ? "bg-primary" : "bg-secondary",
                  )}
                  style={{ height: `${h}%` }}
                />
              </div>
              <span className="font-mono text-xs text-muted-foreground">{w.day}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ---------- next-up reminder ---------- */
function NextUp({ order }: { order?: Order }) {
  return (
    <Card className="flex flex-col">
      <SectionTitle>Próxima ação</SectionTitle>
      <Badge tone={order ? stageTone[order.stage] : "neutral"} className="w-fit">
        {order?.stage ?? "Sem fila"}
      </Badge>
      <h4 className="mt-4 font-display text-2xl font-semibold leading-snug text-foreground">
        {order?.pizzaria ?? "Nenhum pedido"}
        <br />
        {order ? "aguarda avanço" : "aguardando entrada"}
      </h4>
      <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
        <Icon name="chat" size={16} /> via WhatsApp · {order?.updatedAt ?? "sem atualização"} ·{" "}
        {order?.revisions ?? 0}ª revisão
      </p>
      <div className="mt-auto pt-6">
        <Button variant="dark" className="w-full">
          <Icon name="palette" size={16} /> Abrir montagem
        </Button>
      </div>
    </Card>
  );
}

/* ---------- live queue ---------- */
function Queue({ orders }: { orders: Order[] }) {
  return (
    <Card>
      <SectionTitle
        action={
          <button className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs font-medium text-secondary-foreground hover:text-primary">
            <Icon name="plus" size={13} /> Novo
          </button>
        }
      >
        Fila de pedidos
      </SectionTitle>
      <ul className="flex flex-col gap-1">
        {orders.slice(0, 5).map((o) => (
          <li
            key={o.id}
            className="group flex items-center gap-3 rounded-2xl px-2 py-2.5 transition-colors hover:bg-secondary/60"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-secondary text-secondary-foreground">
              <Icon name="box" size={16} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-foreground">{o.pizzaria}</div>
              <div className="font-mono text-[11px] text-muted-foreground">
                {o.id} · {o.boxSize}
              </div>
            </div>
            <Badge tone={stageTone[o.stage]}>{o.stage}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* ---------- CRM classification ---------- */
const crmTones: Record<string, string> = {
  VIP: "bg-accent",
  Recorrente: "bg-[#4f7a3a]",
  "Primeiro pedido": "bg-primary",
  Reativado: "bg-[#b8532f]",
};
function CrmMix({ clients }: { clients: Client[] }) {
  const total = clients.length || 1;
  const crm = ["VIP", "Recorrente", "Primeiro pedido", "Reativado"].map((label) => {
    const count = clients.filter((client) => client.klass === label).length;
    return {
      label,
      value: Math.round((count / total) * 100),
      tone: crmTones[label],
    };
  });

  return (
    <Card>
      <SectionTitle>Carteira de clientes</SectionTitle>
      <div className="flex h-3 w-full overflow-hidden rounded-full">
        {crm.map((c) => (
          <div key={c.label} className={c.tone} style={{ width: `${c.value}%` }} />
        ))}
      </div>
      <ul className="mt-5 grid grid-cols-2 gap-3">
        {crm.map((c) => (
          <li key={c.label} className="flex items-center gap-2">
            <span className={cx("size-2.5 rounded-full", c.tone)} />
            <span className="text-sm text-foreground">{c.label}</span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">{c.value}%</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* ---------- approval gauge ---------- */
function ApprovalRate({ orders }: { orders: Order[] }) {
  const approved = orders.filter((order) => order.stage === "Aprovado" || order.stage === "Impressão").length;
  const rate = orders.length ? Math.round((approved / orders.length) * 100) : 0;
  const revisions =
    orders.length
      ? (orders.reduce((total, order) => total + order.revisions, 0) / orders.length).toFixed(1)
      : "0.0";

  return (
    <Card className="flex flex-col items-center">
      <SectionTitle>Taxa de aprovação</SectionTitle>
      <Gauge value={rate} label="pedidos aprovados ou enviados à impressão" />
      <div className="mt-4 flex w-full justify-around border-t border-border pt-4 text-center">
        <div>
          <div className="font-display text-xl font-semibold text-foreground">{revisions}</div>
          <div className="text-xs text-muted-foreground">revisões / arte</div>
        </div>
        <div>
          <div className="font-display text-xl font-semibold text-foreground">{approved}</div>
          <div className="text-xs text-muted-foreground">aprovados</div>
        </div>
      </div>
    </Card>
  );
}

/* ---------- disk tracker (dark) ---------- */
function DiskTracker() {
  return (
    <Card className="relative overflow-hidden border-transparent bg-ink text-primary-foreground">
      <div className="pointer-events-none absolute -bottom-16 -right-10 size-52 rounded-full bg-primary/25 blur-3xl" />
      <div className="pointer-events-none absolute -top-10 left-10 size-40 rounded-full bg-accent/20 blur-3xl" />
      <div className="relative">
        <SectionTitle>
          <span className="text-primary-foreground">Espaço em disco</span>
        </SectionTitle>
        <div className="font-mono text-5xl font-semibold tracking-tight">142.6 GB</div>
        <p className="mt-2 text-sm text-primary-foreground/60">de 210 GB · 214 arquivos PSD</p>
        <div className="mt-5 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-accent to-primary" style={{ width: "68%" }} />
        </div>
        <div className="mt-4 flex items-center gap-2 text-xs text-primary-foreground/60">
          <Icon name="clock" size={14} /> Limpeza automática de arquivos &gt; 90 dias ativa
        </div>
      </div>
    </Card>
  );
}

export function Dashboard() {
  const { orders, clients } = useAppStore();
  const [newOrderOpen, setNewOrderOpen] = useState(false);
  const activeOrders = orders.filter((order) => order.stage !== "Impressão");
  const waitingApproval = orders.filter((order) => order.stage === "Preview enviado" || order.stage === "Ajustes");
  const approved = orders.filter((order) => order.stage === "Aprovado");
  const nextOrder = orders.find((order) => order.stage === "Ajustes") ?? waitingApproval[0] ?? activeOrders[0];
  const stats: Stat[] = [
    {
      label: "Projetos ativos",
      value: String(activeOrders.length),
      delta: `${orders.length} pedidos cadastrados`,
      icon: "box",
      highlight: true,
    },
    {
      label: "Aguardando aprovação",
      value: String(waitingApproval.length),
      delta: `${orders.filter((order) => order.stage === "Ajustes").length} com ajuste pedido`,
      icon: "clock",
    },
    {
      label: "Aprovados",
      value: String(approved.length),
      delta: `${orders.filter((order) => order.stage === "Impressão").length} em impressão`,
      icon: "check",
    },
    {
      label: "Clientes no CRM",
      value: String(clients.length),
      delta: `${clients.filter((client) => client.klass === "Primeiro pedido").length} primeiro pedido`,
      icon: "database",
    },
  ];

  return (
    <>
      <NewOrderModal open={newOrderOpen} onClose={() => setNewOrderOpen(false)} />
      <PageHeader
        title="Painel"
        subtitle="Acompanhe a produção de artes de caixas — do primeiro oi no WhatsApp até a chapa na impressora."
        actions={
          <>
            <Button variant="outline">
              <Icon name="download" size={16} /> Relatório
            </Button>
            <Button onClick={() => setNewOrderOpen(true)}>
              <Icon name="plus" size={16} /> Novo pedido
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((s) => (
          <StatCard key={s.label} s={s} />
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ThroughputChart />
        </div>
        <NextUp order={nextOrder} />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-4">
        <div className="xl:col-span-2">
          <Queue orders={orders} />
        </div>
        <ApprovalRate orders={orders} />
        <div className="flex flex-col gap-5">
          <CrmMix clients={clients} />
        </div>
      </div>

      <div className="mt-5">
        <DiskTracker />
      </div>
    </>
  );
}
