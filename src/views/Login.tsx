import { useState, type FormEvent } from "react";
import { BrandLogo } from "../components/BrandLogo";
import { Icon } from "../components/ui/Icon";
import { Button } from "../components/ui/primitives";
import { useAppStore } from "../store/AppStore";

const OVEN_IMG =
  "https://images.unsplash.com/photo-1606152196365-d1ce5ea838b5?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1400";

function LoginLogo() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandLogo className="h-10 w-auto [&_path]:fill-white" />
    </div>
  );
}

const fieldCls =
  "w-full rounded-2xl border border-border bg-secondary/40 px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary/50 focus:bg-card focus:outline-none focus:ring-2 focus:ring-ring/20";

export function Login() {
  const { login } = useAppStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Preencha e-mail e senha para continuar.");
      return;
    }
    setLoading(true);
    setTimeout(() => {
      if (login(email, password)) {
        return;
      } else {
        setError("E-mail ou senha incorretos. Confira os acessos de demonstração.");
        setLoading(false);
      }
    }, 550);
  }

  return (
    <div className="grid min-h-screen bg-card lg:grid-cols-2">
      {/* left — atmospheric brand panel */}
      <div className="relative hidden overflow-hidden lg:block">
        <img
          src={OVEN_IMG}
          alt="Fogo em forno a lenha"
          className="absolute inset-0 size-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/70 to-ink/30" />
        <div className="absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_-10%,transparent,rgba(36,26,19,0.55))]" />
        <div className="relative flex h-full flex-col justify-between p-10">
          <LoginLogo />
          <div className="max-w-md">
            <h2 className="font-display text-4xl font-semibold leading-[1.08] text-white">
              Do primeiro oi
              <br />
              à arte aprovada.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-white/70">
              Acompanhe cada caixa de pizza pelo funil — atendimento no WhatsApp, previews
              gerados por IA, ajustes do cliente e o arquivo final pronto para a chapa. Tudo
              em um só painel.
            </p>
          </div>
        </div>
      </div>

      {/* right — form */}
      <div className="flex items-center justify-center px-6 py-12 sm:px-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="inline-flex">
              <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground">
                <Icon name="box" size={20} />
              </span>
            </div>
          </div>

          <h1 className="font-display text-3xl font-semibold text-foreground">Entrar na sua conta</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Acesso restrito à equipe da gráfica.
          </p>

          <form onSubmit={submit} className="mt-8 flex flex-col gap-5" noValidate>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-secondary-foreground">
                E-mail
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="voce@pizzabox.com.br"
                className={fieldCls}
              />
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label htmlFor="password" className="text-sm font-medium text-secondary-foreground">
                  Senha
                </label>
                <button type="button" className="text-xs font-medium text-primary hover:underline">
                  Esqueci a senha
                </button>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className={`${fieldCls} pr-12`}
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-3 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-muted-foreground hover:text-foreground"
                  aria-label={show ? "Ocultar senha" : "Mostrar senha"}
                >
                  <Icon name={show ? "image" : "lock"} size={16} />
                </button>
              </div>
            </div>

            {error && (
              <p className="flex items-center gap-2 rounded-xl bg-primary/10 px-3 py-2.5 text-xs font-medium text-primary">
                <Icon name="help" size={14} /> {error}
              </p>
            )}

            <Button type="submit" disabled={loading} className="mt-1 w-full py-3">
              {loading ? "Entrando…" : "Entrar"}
              {!loading && <Icon name="chevronRight" size={16} />}
            </Button>
          </form>

          <div className="mt-6 rounded-2xl border border-border bg-secondary/40 p-4">
            <p className="mb-2 text-xs font-semibold text-secondary-foreground">
              Acessos de demonstração
            </p>
            <ul className="flex flex-col gap-1 font-mono text-[11px] leading-relaxed text-muted-foreground">
              <li>designer@pizzabox.com.br / design123</li>
              <li>admin@pizzabox.com.br / admin123</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
