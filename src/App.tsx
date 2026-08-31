import { useState, type ReactElement } from "react";
import { Sidebar, type ViewId } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { Dashboard } from "./views/Dashboard";
import { Pedidos } from "./views/Pedidos";
import { Clientes } from "./views/Clientes";
import { Arquivos } from "./views/Arquivos";
import { PreImpressao } from "./views/PreImpressao";
import { Login } from "./views/Login";
import { AppStoreProvider, useAppStore } from "./store/AppStore";

const views: Record<ViewId, () => ReactElement> = {
  painel: Dashboard,
  pedidos: Pedidos,
  clientes: Clientes,
  arquivos: Arquivos,
  preimpressao: PreImpressao,
};

function AppShell() {
  const { user, logout } = useAppStore();
  const [view, setView] = useState<ViewId>("painel");
  const [menuOpen, setMenuOpen] = useState(false);
  const Current = views[view];

  if (!user) {
    return <Login />;
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar
        view={view}
        setView={setView}
        open={menuOpen}
        onNavigate={() => setMenuOpen(false)}
      />

      {menuOpen && (
        <button
          className="fixed inset-0 z-30 bg-ink/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMenuOpen(false)}
          aria-label="Fechar menu"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMenuOpen(true)} onLogout={logout} />
        <main key={view} className="flex-1 animate-[fade_.4s_ease] px-5 py-7 sm:px-8">
          <div className="mx-auto max-w-[1400px]">
            <Current />
          </div>
        </main>
      </div>

      <style>{`@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}`}</style>
    </div>
  );
}

export default function App() {
  return (
    <AppStoreProvider>
      <AppShell />
    </AppStoreProvider>
  );
}
