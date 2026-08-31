import { useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { Icon } from "../components/ui/Icon";
import { Avatar, Badge, Button, Card, cx } from "../components/ui/primitives";
import { classTone, type ClientClass } from "../data";
import { useAppStore } from "../store/AppStore";

const filters: (ClientClass | "Todos")[] = [
  "Todos",
  "VIP",
  "Recorrente",
  "Primeiro pedido",
  "Abandono por preço",
  "Abandono no processo",
  "Reativado",
];

export function Clientes() {
  const { clients } = useAppStore();
  const [active, setActive] = useState<(typeof filters)[number]>("Todos");
  const rows = clients.filter((c) => active === "Todos" || c.klass === active);

  return (
    <>
      <PageHeader
        title="Clientes & CRM"
        subtitle="Todo contato pelo WhatsApp vira ficha automaticamente. A IA classifica e reengaja quem some no meio do fluxo."
        actions={
          <Button>
            <Icon name="chat" size={16} /> Disparo de reengajamento
          </Button>
        }
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setActive(f)}
            className={cx(
              "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
              active === f
                ? "border-transparent bg-ink text-primary-foreground"
                : "border-border bg-card text-secondary-foreground hover:border-primary/40",
            )}
          >
            {f}
          </button>
        ))}
      </div>

      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-6 py-4 font-medium">Pizzaria</th>
                <th className="px-4 py-4 font-medium">Contato</th>
                <th className="px-4 py-4 font-medium">Classificação</th>
                <th className="px-4 py-4 font-medium">Pedidos</th>
                <th className="px-4 py-4 font-medium">Último contato</th>
                <th className="px-6 py-4" />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.name}
                  className="group border-b border-border/60 transition-colors last:border-0 hover:bg-secondary/40"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <Avatar name={c.name} size={38} />
                      <div>
                        <div className="font-medium text-foreground">{c.name}</div>
                        <div className="font-mono text-[11px] text-muted-foreground">{c.phone}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-secondary-foreground">{c.contact}</td>
                  <td className="px-4 py-4">
                    <Badge tone={classTone[c.klass]}>{c.klass}</Badge>
                  </td>
                  <td className="px-4 py-4 font-mono text-foreground">{c.orders}</td>
                  <td className="px-4 py-4 text-muted-foreground">{c.lastContact}</td>
                  <td className="px-6 py-4 text-right">
                    <button
                      className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-secondary-foreground opacity-0 transition-opacity hover:text-primary group-hover:opacity-100"
                    >
                      <Icon name="chevronRight" size={13} /> Ficha
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="mt-4 text-xs text-muted-foreground">
        Mostrando {rows.length} de {clients.length} clientes · Mensagens de acompanhamento
        automáticas enviadas a quem não responde há 48 h.
      </p>
    </>
  );
}
