import { PageHeader } from "../components/PageHeader";
import { Icon } from "../components/ui/Icon";
import { Badge, Button, Card, SectionTitle, cx, type Tone } from "../components/ui/primitives";
import { PSD_FILES } from "../data";

const statusTone: Record<string, Tone> = {
  Aprovado: "basil",
  "Em ajuste": "cheese",
  Arquivado: "neutral",
};

function UsageCard() {
  return (
    <Card className="relative overflow-hidden border-transparent bg-ink text-primary-foreground">
      <div className="pointer-events-none absolute -right-10 -top-10 size-48 rounded-full bg-primary/25 blur-3xl" />
      <div className="relative">
        <div className="flex items-center gap-2 text-sm text-primary-foreground/70">
          <Icon name="database" size={16} /> Armazenamento total
        </div>
        <div className="mt-3 flex items-end gap-2">
          <span className="font-mono text-4xl font-semibold">142.6</span>
          <span className="mb-1 text-primary-foreground/60">/ 210 GB</span>
        </div>
        <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-accent to-primary" style={{ width: "68%" }} />
        </div>
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-primary-foreground/70">
          <Icon name="clock" size={14} className="text-accent" />
          Alerta de capacidade dispara em 85% · retenção: excluir &gt; 90 dias
        </div>
      </div>
    </Card>
  );
}

function Spark({ data }: { data: number[] }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 28 - ((v - min) / span) * 24 - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="mt-3 h-8 w-full" aria-hidden>
      <polyline
        points={pts}
        fill="none"
        stroke="var(--primary)"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={100} cy={Number(pts.split(" ").pop()!.split(",")[1])} r={2.5} fill="var(--primary)" />
    </svg>
  );
}

function MiniStat({
  label,
  value,
  sub,
  spark,
}: {
  label: string;
  value: string;
  sub: string;
  spark?: number[];
}) {
  return (
    <Card>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{sub}</div>
      {spark && <Spark data={spark} />}
    </Card>
  );
}

export function Arquivos() {
  return (
    <>
      <PageHeader
        title="Arquivos PSD"
        subtitle="O editável final fica só aqui dentro. Nunca vai para o cliente — é o que garante a exclusividade do serviço."
        actions={
          <Button variant="outline">
            <Icon name="filter" size={16} /> Filtros
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="lg:col-span-2">
          <UsageCard />
        </div>
        <MiniStat
          label="Arquivos gerados"
          value="214"
          sub="+9 nos últimos 7 dias"
          spark={[182, 188, 193, 197, 201, 205, 214]}
        />
        <MiniStat
          label="Maior arquivo"
          value="3.1 GB"
          sub="redonda_40cm_hi-res.psd"
          spark={[1.2, 1.6, 1.8, 2.1, 2.3, 2.8, 3.1]}
        />
      </div>

      <Card className="mt-5 p-0">
        <div className="flex items-center justify-between px-6 pt-6">
          <SectionTitle>Arquivos recentes</SectionTitle>
          <Badge tone="ink">
            <Icon name="lock" size={12} /> Uso interno
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-6 py-3 font-medium">Arquivo</th>
                <th className="px-4 py-3 font-medium">Cliente</th>
                <th className="px-4 py-3 font-medium">Tamanho</th>
                <th className="px-4 py-3 font-medium">Criado</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {PSD_FILES.map((f) => (
                <tr key={f.name} className="group border-b border-border/60 transition-colors last:border-0 hover:bg-secondary/40">
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 font-mono text-[10px] font-semibold text-primary">
                        PSD
                      </span>
                      <span className="font-mono text-[13px] text-foreground">{f.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-secondary-foreground">{f.client}</td>
                  <td className="px-4 py-3.5 font-mono text-foreground">{f.size.toFixed(1)} GB</td>
                  <td className="px-4 py-3.5 text-muted-foreground">{f.created}</td>
                  <td className="px-4 py-3.5">
                    <Badge tone={statusTone[f.status]}>{f.status}</Badge>
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      <button className="grid size-8 place-items-center rounded-full text-secondary-foreground hover:bg-secondary hover:text-primary" aria-label="Baixar">
                        <Icon name="download" size={15} />
                      </button>
                      <button className="grid size-8 place-items-center rounded-full text-secondary-foreground hover:bg-primary/10 hover:text-primary" aria-label="Excluir">
                        <Icon name="trash" size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
