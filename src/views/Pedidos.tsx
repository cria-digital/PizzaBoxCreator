import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { NewOrderModal } from "../components/NewOrderModal";
import { FiltersDrawer } from "../components/FiltersDrawer";
import { Icon } from "../components/ui/Icon";
import { Badge, Button, cx } from "../components/ui/primitives";
import { LAYERS, STAGES, stageTone, type Order, type Stage } from "../data";
import { useAppStore } from "../store/AppStore";

function OrderCard({
  o,
  onStageChange,
}: {
  o: Order;
  onStageChange: (orderId: string, stage: Stage) => void;
}) {
  return (
    <article className="group cursor-pointer rounded-2xl border border-border/70 bg-card p-4 shadow-[0_10px_30px_-28px_rgba(42,33,26,0.6)] transition-all hover:-translate-y-0.5 hover:border-primary/40">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] text-muted-foreground">{o.id}</span>
        <button className="text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" aria-label="Opções">
          <Icon name="dots" size={16} />
        </button>
      </div>
      <h4 className="mt-1 font-display text-base font-semibold text-foreground">{o.pizzaria}</h4>
      <p className="text-xs text-muted-foreground">{o.city}</p>
      <div className="mt-3 flex items-center gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Icon name="ruler" size={13} /> {o.boxSize}
        </span>
        <span className="inline-flex items-center gap-1">
          <Icon name="palette" size={13} /> {o.revisions} rev.
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3">
        <span className="text-[11px] text-muted-foreground">{o.updatedAt}</span>
        <select
          value={o.stage}
          onChange={(event) => onStageChange(o.id, event.target.value as Stage)}
          className="max-w-[136px] rounded-full border border-border bg-secondary/40 px-2 py-1 text-[11px] text-secondary-foreground outline-none transition-colors hover:border-primary/40"
          aria-label={`Etapa do pedido ${o.id}`}
        >
          {STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {stage}
            </option>
          ))}
        </select>
      </div>
    </article>
  );
}

export function Pedidos() {
  const { orders, updateOrderStage } = useAppStore();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [newOrderOpen, setNewOrderOpen] = useState(false);
  return (
    <>
      <NewOrderModal open={newOrderOpen} onClose={() => setNewOrderOpen(false)} />
      <FiltersDrawer open={filtersOpen} onClose={() => setFiltersOpen(false)} />
      <PageHeader
        title="Pedidos"
        subtitle="Cada caixa avança por etapas fixas. Arraste mentalmente da esquerda para a direita — do atendimento à impressão."
        actions={
          <>
            <Button variant="outline" onClick={() => setFiltersOpen(true)}>
              <Icon name="filter" size={16} /> Filtrar
            </Button>
            <Button onClick={() => setNewOrderOpen(true)}>
              <Icon name="plus" size={16} /> Novo pedido
            </Button>
          </>
        }
      />

      <div className="-mx-1 flex gap-4 overflow-x-auto px-1 pb-4">
        {STAGES.map((stage) => {
          const items = orders.filter((o) => o.stage === stage);
          return (
            <section key={stage} className="flex w-[264px] shrink-0 flex-col gap-3">
              <header className="flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <Badge tone={stageTone[stage]} dot>
                    {stage}
                  </Badge>
                </div>
                <span className="font-mono text-xs text-muted-foreground">{items.length}</span>
              </header>
              <div className="flex flex-col gap-3">
                {items.map((o) => (
                  <OrderCard key={o.id} o={o} onStageChange={updateOrderStage} />
                ))}
                {items.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
                    Sem pedidos
                  </div>
                )}
              </div>
            </section>
          );
        })}
      </div>

      {/* layer structure reference */}
      <div className="mt-6 rounded-[var(--radius)] border border-border/70 bg-card p-6">
        <div className="mb-4 flex items-center gap-2">
          <Icon name="layers" size={18} className="text-primary" />
          <h3 className="font-display text-lg font-semibold">Estrutura de camadas do template</h3>
          <Badge tone="ink" className="ml-auto">
            <Icon name="lock" size={12} /> Posições travadas
          </Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          {LAYERS.map((l, i) => (
            <span
              key={l}
              className={cx(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
                l === "Marca d'água"
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-secondary/50 text-secondary-foreground",
              )}
            >
              <span className="font-mono text-[10px] text-muted-foreground">
                {String(i + 1).padStart(2, "0")}
              </span>
              {l}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
