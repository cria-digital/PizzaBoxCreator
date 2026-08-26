import { PageHeader } from "../components/PageHeader";
import { Icon } from "../components/ui/Icon";
import { Badge, Button, Card, SectionTitle } from "../components/ui/primitives";

const faca = [
  { label: "Faca de corte", color: "#e10098", desc: "Magenta 100% · Pantone spot", spot: "Corte" },
  { label: "Vinco / dobra", color: "#00a2e8", desc: "Ciano 100% · linha tracejada", spot: "Vinco" },
  { label: "Serrilha", color: "#39b54a", desc: "Verde spot · picote", spot: "Serrilha" },
];

const cmyk = [
  { k: "C", v: 12, color: "#00a2e8" },
  { k: "M", v: 86, color: "#e10098" },
  { k: "Y", v: 74, color: "#f7e017" },
  { k: "K", v: 8, color: "#1c1c1c" },
];

function Field({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-border bg-secondary/40 px-4 py-3">
      <span className="text-sm text-secondary-foreground">{label}</span>
      <span className="font-mono text-sm font-medium text-foreground">
        {value}
        <span className="ml-1 text-muted-foreground">{unit}</span>
      </span>
    </div>
  );
}

export function PreImpressao() {
  return (
    <>
      <PageHeader
        title="Pré-impressão"
        subtitle="Parâmetros técnicos que a IA respeita em toda arte: perfil de cor, cores das facas e área de sangria. Ajuste pela gráfica."
        actions={
          <Button>
            <Icon name="check" size={16} /> Salvar perfil
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* CMYK profile */}
        <Card>
          <SectionTitle action={<Badge tone="ink">FOGRA39</Badge>}>Perfil de cor</SectionTitle>
          <p className="text-sm text-muted-foreground">
            Toda cor escolhida no WhatsApp é convertida para CMYK antes de gerar a chapa.
          </p>
          <div className="mt-5 flex flex-col gap-3">
            {cmyk.map((c) => (
              <div key={c.k} className="flex items-center gap-3">
                <span
                  className="grid size-7 place-items-center rounded-md font-mono text-xs font-semibold text-white"
                  style={{ background: c.color }}
                >
                  {c.k}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full" style={{ width: `${c.v}%`, background: c.color }} />
                </div>
                <span className="w-10 text-right font-mono text-xs text-muted-foreground">{c.v}%</span>
              </div>
            ))}
          </div>
          <p className="mt-5 rounded-xl bg-secondary/60 px-3 py-2 text-xs text-muted-foreground">
            Amostra: <span className="font-mono text-foreground">Vermelho tomate</span> → C12 M86 Y74 K8
          </p>
        </Card>

        {/* die-line colors */}
        <Card>
          <SectionTitle action={<Icon name="scissors" size={18} className="text-primary" />}>
            Cores das facas
          </SectionTitle>
          <p className="text-sm text-muted-foreground">
            Linhas técnicas usam cores spot separadas para não sair na impressão.
          </p>
          <ul className="mt-5 flex flex-col gap-3">
            {faca.map((f) => (
              <li key={f.label} className="flex items-center gap-3 rounded-2xl border border-border p-3">
                <span className="size-9 shrink-0 rounded-lg" style={{ background: f.color }} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-foreground">{f.label}</div>
                  <div className="truncate text-xs text-muted-foreground">{f.desc}</div>
                </div>
                <Badge tone="neutral">{f.spot}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        {/* bleed */}
        <Card>
          <SectionTitle>Sangria & margens</SectionTitle>
          <p className="text-sm text-muted-foreground">
            A IA garante que nenhum elemento ultrapasse a área segura da faca.
          </p>
          <div className="mt-5 flex flex-col gap-3">
            <Field label="Sangria" value="3" unit="mm" />
            <Field label="Margem de segurança" value="5" unit="mm" />
            <Field label="Área útil da tampa" value="345 × 345" unit="mm" />
          </div>
          <div className="mt-4 grid place-items-center rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5 p-6">
            <div className="grid w-full max-w-[160px] place-items-center rounded-lg border-2 border-primary bg-card p-5 text-center">
              <span className="text-xs font-medium text-foreground">Área imprimível</span>
              <span className="font-mono text-[10px] text-muted-foreground">margem 5mm · sangria 3mm</span>
            </div>
          </div>
        </Card>
      </div>

      {/* coin calibration */}
      <Card className="mt-5">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
          <div className="flex-1">
            <div className="mb-3 flex items-center gap-2">
              <span className="grid size-9 place-items-center rounded-full bg-accent/15 text-[#9c6a12]">
                <Icon name="coin" size={18} />
              </span>
              <h3 className="font-display text-xl font-semibold">Calibração inteligente por foto</h3>
              <Badge tone="sauce" dot>
                IA
              </Badge>
            </div>
            <p className="max-w-xl text-sm text-muted-foreground">
              O cliente fotografa a tampa da caixa com uma moeda de R$1 em cima. A IA usa a moeda
              como escala para medir a embalagem e ajustar o layout automaticamente — reduzindo
              erros de proporção na impressão.
            </p>
            <div className="mt-5 grid grid-cols-3 gap-3">
              <Field label="Largura" value="352" unit="mm" />
              <Field label="Altura" value="348" unit="mm" />
              <Field label="Escala" value="R$1 ⌀27" unit="mm" />
            </div>
          </div>
          <div className="grid aspect-square w-full max-w-[220px] place-items-center rounded-2xl border border-border bg-secondary/50">
            <div className="relative grid size-32 place-items-center rounded-xl bg-[#c69a6d] shadow-inner">
              <div className="absolute inset-3 rounded-md border-2 border-dashed border-white/50" />
              <span className="grid size-9 place-items-center rounded-full bg-accent font-mono text-[10px] font-bold text-ink shadow-lg">
                R$1
              </span>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}
