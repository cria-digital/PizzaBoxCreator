import { Icon } from "./ui/Icon";
import { Avatar } from "./ui/primitives";

export function Topbar({ onMenu, onLogout }: { onMenu: () => void; onLogout?: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border/60 bg-background/80 px-5 py-4 backdrop-blur-md sm:gap-4 sm:px-8">
      <button
        onClick={onMenu}
        className="grid size-10 shrink-0 place-items-center rounded-full border border-border bg-card text-foreground lg:hidden"
        aria-label="Abrir menu"
      >
        <Icon name="grid" size={18} />
      </button>

      <label className="relative flex flex-1 items-center">
        <span className="pointer-events-none absolute left-4 text-muted-foreground">
          <Icon name="search" size={18} />
        </span>
        <input
          type="search"
          placeholder="Buscar pedido, pizzaria ou arquivo…"
          className="h-11 w-full rounded-full border border-border/80 bg-card pl-11 pr-16 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring/25"
        />
        <kbd className="pointer-events-none absolute right-3 hidden rounded-md border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
          ⌘K
        </kbd>
      </label>

      <div className="flex items-center gap-2 sm:gap-3">
        <button
          className="relative grid size-11 place-items-center rounded-full border border-border bg-card text-secondary-foreground transition-colors hover:text-primary"
          aria-label="Mensagens"
        >
          <Icon name="mail" size={18} />
        </button>
        <button
          className="relative grid size-11 place-items-center rounded-full border border-border bg-card text-secondary-foreground transition-colors hover:text-primary"
          aria-label="Notificações"
        >
          <Icon name="bell" size={18} />
          <span className="absolute right-2.5 top-2.5 size-2 rounded-full bg-primary ring-2 ring-card" />
        </button>
        <div className="ml-1 flex items-center gap-3 rounded-full border border-border bg-card py-1 pl-1 pr-4">
          <Avatar name="Marina Costa" size={36} />
          <div className="hidden leading-tight sm:block">
            <div className="text-sm font-semibold text-foreground">Marina Costa</div>
            <div className="text-xs text-muted-foreground">Designer · Gráfica</div>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="grid size-11 place-items-center rounded-full border border-border bg-card text-secondary-foreground transition-colors hover:border-primary/40 hover:text-primary"
          aria-label="Sair"
        >
          <Icon name="logout" size={18} />
        </button>
      </div>
    </header>
  );
}
