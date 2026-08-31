import { BrandLogo } from "./BrandLogo";
import { Icon, type IconName } from "./ui/Icon";
import { cx } from "./ui/primitives";
import { useAppStore } from "../store/AppStore";

export type ViewId =
  | "painel"
  | "pedidos"
  | "clientes"
  | "arquivos"
  | "preimpressao";

const primary: { id: ViewId; label: string; icon: IconName; badge?: string }[] = [
  { id: "painel", label: "Painel", icon: "grid" },
  { id: "pedidos", label: "Pedidos", icon: "box" },
  { id: "clientes", label: "Clientes & CRM", icon: "users" },
  { id: "arquivos", label: "Arquivos PSD", icon: "layers" },
  { id: "preimpressao", label: "Pré-impressão", icon: "printer" },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-1">
      <BrandLogo className="h-11 w-auto" />
    </div>
  );
}

export function Sidebar({
  view,
  setView,
  open,
  onNavigate,
}: {
  view: ViewId;
  setView: (v: ViewId) => void;
  open: boolean;
  onNavigate: () => void;
}) {
  const { orders } = useAppStore();
  const openOrders = orders.filter((order) => order.stage !== "Impressão").length;

  return (
    <aside
      className={cx(
        "fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col gap-8 border-r border-border/70 bg-card/70 px-5 pt-4 backdrop-blur-sm transition-transform duration-300 lg:static lg:translate-x-0",
        open ? "translate-x-0" : "-translate-x-full",
      )}
    >
      <Logo />

      <nav className="flex flex-1 flex-col gap-8 overflow-y-auto">
        <div>
          <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Operação
          </p>
          <ul className="flex flex-col gap-1">
            {primary.map((item) => {
              const badge = item.id === "pedidos" ? String(openOrders) : item.badge;
              const active = view === item.id;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => {
                      setView(item.id);
                      onNavigate();
                    }}
                    className={cx(
                      "group relative flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-medium transition-colors",
                      active
                        ? "bg-primary/10 text-primary"
                        : "text-secondary-foreground hover:bg-secondary",
                    )}
                  >
                    {active && (
                      <span className="absolute -left-5 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
                    )}
                    <Icon name={item.icon} size={19} />
                    <span className="flex-1 text-left">{item.label}</span>
                    {badge && (
                      <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                        {badge}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>

      {/* WhatsApp channel status card */}
      <div className="relative overflow-hidden rounded-[var(--radius)] bg-ink p-5 text-primary-foreground">
        <div className="absolute -right-8 -top-8 size-28 rounded-full bg-primary/30 blur-2xl" />
        <div className="relative">
          <div className="flex items-center gap-2">
            <span className="grid size-8 place-items-center rounded-full bg-[#25D366]/20 text-[#4ade80]">
              <Icon name="chat" size={16} />
            </span>
            <span className="text-sm font-medium">Canal WhatsApp</span>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-primary-foreground/60">
            IA atendendo em tempo real. 3 conversas aguardando ajuste.
          </p>
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-[#4ade80]">
            <span className="size-1.5 animate-pulse rounded-full bg-[#4ade80]" />
            Online
          </div>
        </div>
      </div>
    </aside>
  );
}
