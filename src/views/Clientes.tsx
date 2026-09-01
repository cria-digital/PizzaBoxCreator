import { useMemo, useState, type FormEvent } from "react";
import { PageHeader } from "../components/PageHeader";
import { Icon } from "../components/ui/Icon";
import { Avatar, Badge, Button, Card, cx } from "../components/ui/primitives";
import { classTone, type Client, type ClientClass } from "../data";
import { useAppStore, type ClientFormInput } from "../store/AppStore";

const filters: (ClientClass | "Todos")[] = [
  "Todos",
  "VIP",
  "Recorrente",
  "Primeiro pedido",
  "Abandono por preço",
  "Abandono no processo",
  "Reativado",
];

const emptyForm: ClientFormInput = {
  name: "",
  phone: "",
  instagram: "",
  logoPath: null,
};

function onlyDigits(value: string) {
  return value.replace(/\D/g, "");
}

function validateClient(input: ClientFormInput) {
  if (input.name.trim().length < 2) return "Informe o nome da pizzaria.";
  const phone = onlyDigits(input.phone);
  if (phone.length < 10 || phone.length > 14) return "Informe um telefone valido.";
  return "";
}

function formFromClient(client: Client): ClientFormInput {
  return {
    name: client.name,
    phone: client.phone,
    instagram: client.instagram || "",
    logoPath: client.logoPath || null,
  };
}

function ClientModal({
  client,
  saving,
  error,
  onClose,
  onSubmit,
}: {
  client: Client | null;
  saving: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (input: ClientFormInput) => Promise<void>;
}) {
  const [form, setForm] = useState<ClientFormInput>(() => client ? formFromClient(client) : emptyForm);
  const [localError, setLocalError] = useState("");
  const title = client ? "Editar cliente" : "Novo cliente";

  async function submit(event: FormEvent) {
    event.preventDefault();
    const validation = validateClient(form);
    if (validation) {
      setLocalError(validation);
      return;
    }
    setLocalError("");
    await onSubmit({
      ...form,
      name: form.name.trim(),
      phone: onlyDigits(form.phone),
      instagram: form.instagram?.trim(),
    });
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-4 py-8 backdrop-blur-sm">
      <form
        onSubmit={submit}
        className="w-full max-w-xl rounded-[var(--radius)] border border-border bg-card p-6 shadow-[0_22px_70px_-30px_rgba(42,33,26,.55)]"
      >
        <div className="mb-5 flex items-center justify-between gap-4">
          <h2 className="font-display text-2xl font-semibold text-foreground">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="grid size-10 place-items-center rounded-full border border-border text-secondary-foreground hover:text-primary"
            aria-label="Fechar"
          >
            <Icon name="plus" size={18} className="rotate-45" />
          </button>
        </div>

        <div className="grid gap-4">
          <label className="grid gap-1.5 text-sm font-medium text-secondary-foreground">
            Nome da pizzaria
            <input
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              className="h-11 rounded-xl border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary/60 focus:ring-2 focus:ring-ring/20"
              autoFocus
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="grid gap-1.5 text-sm font-medium text-secondary-foreground">
              Telefone / WhatsApp
              <input
                value={form.phone}
                onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))}
                className="h-11 rounded-xl border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary/60 focus:ring-2 focus:ring-ring/20"
                inputMode="tel"
              />
            </label>

            <label className="grid gap-1.5 text-sm font-medium text-secondary-foreground">
              Instagram
              <input
                value={form.instagram || ""}
                onChange={(event) => setForm((current) => ({ ...current, instagram: event.target.value }))}
                className="h-11 rounded-xl border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-primary/60 focus:ring-2 focus:ring-ring/20"
                placeholder="@pizzaria"
              />
            </label>
          </div>
        </div>

        {(localError || error) && (
          <p className="mt-4 rounded-xl bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
            {localError || error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            <Icon name="check" size={16} />
            {saving ? "Salvando..." : "Salvar"}
          </Button>
        </div>
      </form>
    </div>
  );
}

export function Clientes() {
  const { clients, createClient, updateClient, deleteClient, loadingData } = useAppStore();
  const [active, setActive] = useState<(typeof filters)[number]>("Todos");
  const [editing, setEditing] = useState<Client | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return clients.filter((client) => {
      const matchesFilter = active === "Todos" || client.klass === active;
      const matchesSearch = !q
        || client.name.toLowerCase().includes(q)
        || client.phone.includes(q)
        || (client.instagram || "").toLowerCase().includes(q);
      return matchesFilter && matchesSearch;
    });
  }, [active, clients, query]);

  function openCreate() {
    setEditing(null);
    setError("");
    setModalOpen(true);
  }

  function openEdit(client: Client) {
    setEditing(client);
    setError("");
    setModalOpen(true);
  }

  async function submitClient(input: ClientFormInput) {
    setSaving(true);
    setError("");
    try {
      if (editing) {
        await updateClient(editing, input);
      } else {
        await createClient(input);
      }
      setModalOpen(false);
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar cliente");
    } finally {
      setSaving(false);
    }
  }

  async function removeClient(client: Client) {
    setError("");
    try {
      await deleteClient(client);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir cliente");
    }
  }

  return (
    <>
      <PageHeader
        title="Clientes & CRM"
        subtitle="Cadastro operacional de pizzarias, contatos e histórico de pedidos."
        actions={
          <Button onClick={openCreate}>
            <Icon name="plus" size={16} /> Novo cliente
          </Button>
        }
      />

      <div className="mb-5 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-2">
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

        <label className="relative w-full xl:max-w-sm">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
            <Icon name="search" size={16} />
          </span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar cliente..."
            className="h-10 w-full rounded-full border border-border bg-card pl-10 pr-4 text-sm text-foreground outline-none focus:border-primary/50 focus:ring-2 focus:ring-ring/20"
          />
        </label>
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm font-medium text-primary">
          {error}
        </p>
      )}

      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-6 py-4 font-medium">Pizzaria</th>
                <th className="px-4 py-4 font-medium">Contato</th>
                <th className="px-4 py-4 font-medium">Classificação</th>
                <th className="px-4 py-4 font-medium">Pedidos</th>
                <th className="px-4 py-4 font-medium">Último contato</th>
                <th className="px-6 py-4 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((client) => (
                <tr
                  key={client.id ?? client.phone}
                  className="group border-b border-border/60 transition-colors last:border-0 hover:bg-secondary/40"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <Avatar name={client.name} size={38} />
                      <div>
                        <div className="font-medium text-foreground">{client.name}</div>
                        <div className="font-mono text-[11px] text-muted-foreground">{client.phone}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-secondary-foreground">
                    <div>{client.contact}</div>
                    {client.instagram && (
                      <div className="font-mono text-[11px] text-muted-foreground">{client.instagram}</div>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <Badge tone={classTone[client.klass]}>{client.klass}</Badge>
                  </td>
                  <td className="px-4 py-4 font-mono text-foreground">{client.orders}</td>
                  <td className="px-4 py-4 text-muted-foreground">{client.lastContact}</td>
                  <td className="px-6 py-4">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => openEdit(client)}
                        className="inline-flex size-9 items-center justify-center rounded-full border border-border text-secondary-foreground hover:border-primary/40 hover:text-primary"
                        aria-label={`Editar ${client.name}`}
                      >
                        <Icon name="settings" size={15} />
                      </button>
                      <button
                        onClick={() => void removeClient(client)}
                        disabled={client.orders > 0}
                        className="inline-flex size-9 items-center justify-center rounded-full border border-border text-secondary-foreground hover:border-primary/40 hover:text-primary disabled:cursor-not-allowed disabled:opacity-35"
                        aria-label={`Excluir ${client.name}`}
                        title={client.orders > 0 ? "Cliente com pedidos nao pode ser excluido" : "Excluir cliente"}
                      >
                        <Icon name="trash" size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-sm text-muted-foreground">
                    Nenhum cliente encontrado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="mt-4 text-xs text-muted-foreground">
        Mostrando {rows.length} de {clients.length} clientes
        {loadingData ? " · atualizando dados..." : ""}
      </p>

      {modalOpen && (
        <ClientModal
          key={editing?.id ?? "new"}
          client={editing}
          saving={saving}
          error={error}
          onClose={() => {
            setModalOpen(false);
            setEditing(null);
            setError("");
          }}
          onSubmit={submitClient}
        />
      )}
    </>
  );
}
