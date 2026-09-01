import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { NewOrderModal } from "../components/NewOrderModal";
import { FiltersDrawer } from "../components/FiltersDrawer";
import { Icon } from "../components/ui/Icon";
import { Badge, Button, cx } from "../components/ui/primitives";
import { LAYERS, STAGES, stageTone, type Order, type Stage } from "../data";
import type { AuditEntry, OrderFile } from "../data";
import { useAppStore } from "../store/AppStore";

function OrderCard({
  o,
  onStageChange,
  onSelect,
}: {
  o: Order;
  onStageChange: (orderId: string, stage: Stage) => Promise<void>;
  onSelect: (order: Order) => void;
}) {
  return (
    <article
      className="group cursor-pointer rounded-2xl border border-border/70 bg-card p-4 shadow-[0_10px_30px_-28px_rgba(42,33,26,0.6)] transition-all hover:-translate-y-0.5 hover:border-primary/40"
      onClick={() => onSelect(o)}
    >
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
        {o.quantity && (
          <span className="inline-flex items-center gap-1">
            <Icon name="database" size={13} /> {o.quantity}
          </span>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between border-t border-border/60 pt-3">
        <span className="text-[11px] text-muted-foreground">{o.updatedAt}</span>
        <select
          value={o.stage}
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            event.stopPropagation();
            void onStageChange(o.id, event.target.value as Stage);
          }}
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

function actionLabel(action: string) {
  const labels: Record<string, string> = {
    order_created: "Pedido criado",
    order_status_updated: "Etapa alterada",
    order_approved: "Pedido aprovado",
    order_rejected: "Pedido rejeitado",
    "file_uploaded:logo": "Logo enviada",
    "file_uploaded:reference": "Referência enviada",
  };
  return labels[action] ?? action;
}

export function Pedidos() {
  const { backendEnabled, listOrderAudit, listOrderFiles, orders, updateOrderStage } = useAppStore();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [newOrderOpen, setNewOrderOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [orderFiles, setOrderFiles] = useState<OrderFile[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [stageError, setStageError] = useState("");

  async function changeStage(orderId: string, stage: Stage) {
    setStageError("");
    try {
      await updateOrderStage(orderId, stage);
      if (selectedOrder?.id === orderId && backendEnabled) {
        const [files, entries] = await Promise.all([
          listOrderFiles(orderId),
          listOrderAudit(orderId),
        ]);
        setOrderFiles(files);
        setAudit(entries);
      }
    } catch (error) {
      setStageError(error instanceof Error ? error.message : "Falha ao atualizar etapa");
    }
  }

  useEffect(() => {
    if (!backendEnabled || !selectedOrder) {
      setOrderFiles([]);
      setAudit([]);
      return;
    }

    let active = true;
    Promise.all([
      listOrderFiles(selectedOrder.id),
      listOrderAudit(selectedOrder.id),
    ])
      .then(([files, entries]) => {
        if (!active) return;
        setOrderFiles(files);
        setAudit(entries);
      })
      .catch(() => {
        if (!active) return;
        setOrderFiles([]);
        setAudit([]);
      });

    return () => {
      active = false;
    };
  }, [backendEnabled, selectedOrder?.id]);

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

      {stageError && (
        <div className="mb-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-medium text-primary">
          {stageError}
        </div>
      )}

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
                  <OrderCard key={o.id} o={o} onStageChange={changeStage} onSelect={setSelectedOrder} />
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

      {selectedOrder && (
        <section className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-[var(--radius)] border border-border/70 bg-card p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-mono text-xs text-muted-foreground">{selectedOrder.id}</div>
                <h3 className="mt-1 font-display text-xl font-semibold text-foreground">
                  {selectedOrder.pizzaria}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {selectedOrder.templateName ?? selectedOrder.boxSize} · {selectedOrder.city}
                </p>
              </div>
              <Badge tone={stageTone[selectedOrder.stage]} dot>
                {selectedOrder.stage}
              </Badge>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-2xl border border-border bg-secondary/40 px-4 py-3">
                <div className="text-xs text-muted-foreground">Quantidade</div>
                <div className="mt-1 font-mono text-sm text-foreground">{selectedOrder.quantity ?? "—"}</div>
              </div>
              <div className="rounded-2xl border border-border bg-secondary/40 px-4 py-3">
                <div className="text-xs text-muted-foreground">Revisões</div>
                <div className="mt-1 font-mono text-sm text-foreground">{selectedOrder.revisions}</div>
              </div>
              <div className="rounded-2xl border border-border bg-secondary/40 px-4 py-3">
                <div className="text-xs text-muted-foreground">Atualizado</div>
                <div className="mt-1 font-mono text-sm text-foreground">{selectedOrder.updatedAt}</div>
              </div>
              <div className="rounded-2xl border border-border bg-secondary/40 px-4 py-3">
                <div className="text-xs text-muted-foreground">Arquivos</div>
                <div className="mt-1 font-mono text-sm text-foreground">{orderFiles.length}</div>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {orderFiles.map((file) => (
                <a
                  key={`${file.kind}:${file.filename}`}
                  href={file.downloadUrl}
                  className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  <Icon name="download" size={13} /> {file.filename}
                </a>
              ))}
              {orderFiles.length === 0 && (
                <span className="text-sm text-muted-foreground">Nenhum arquivo associado ainda.</span>
              )}
            </div>
          </div>

          <div className="rounded-[var(--radius)] border border-border/70 bg-card p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 className="font-display text-lg font-semibold text-foreground">Auditoria</h3>
              <Badge tone={backendEnabled ? "basil" : "neutral"}>{backendEnabled ? "Banco" : "Local"}</Badge>
            </div>
            <ul className="flex max-h-[280px] flex-col gap-3 overflow-y-auto pr-1">
              {audit.map((entry) => (
                <li key={entry.id} className="rounded-2xl border border-border bg-secondary/30 px-3 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-foreground">{actionLabel(entry.action)}</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{entry.createdAt}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{entry.username}</div>
                </li>
              ))}
              {audit.length === 0 && (
                <li className="rounded-2xl border border-dashed border-border py-6 text-center text-xs text-muted-foreground">
                  Selecione um pedido salvo no backend para ver o histórico.
                </li>
              )}
            </ul>
          </div>
        </section>
      )}

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
