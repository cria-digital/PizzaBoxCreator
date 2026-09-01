import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { PageHeader } from "../components/PageHeader";
import { Icon } from "../components/ui/Icon";
import { Badge, Card, SectionTitle, cx, type Tone } from "../components/ui/primitives";
import { PSD_FILES, stageTone, type Order, type OrderFile } from "../data";
import { useAppStore } from "../store/AppStore";

const fileKindLabel: Record<string, string> = {
  preview: "Preview",
  production: "Produção",
  package: "Pacote",
  source: "Fonte",
  logo: "Logo",
};

const mockStatusTone: Record<string, Tone> = {
  Aprovado: "basil",
  "Em ajuste": "cheese",
  Arquivado: "neutral",
};

function kindLabel(kind: string) {
  if (kind.startsWith("reference:")) return "Referência";
  return fileKindLabel[kind] ?? kind;
}

function extension(filename: string) {
  const ext = filename.split(".").pop();
  return ext ? ext.slice(0, 4).toUpperCase() : "FILE";
}

function BackendUsage({
  fileCount,
  selectedOrder,
}: {
  fileCount: number;
  selectedOrder: Order | null;
}) {
  return (
    <Card className="border-transparent bg-ink text-primary-foreground">
      <div className="flex items-center gap-2 text-sm text-primary-foreground/70">
        <Icon name="database" size={16} /> Storage conectado
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-4xl font-semibold">{fileCount}</span>
        <span className="mb-1 text-primary-foreground/60">arquivo(s)</span>
      </div>
      <div className="mt-4 flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-primary-foreground/70">
        <Icon name="lock" size={14} className="text-accent" />
        {selectedOrder ? `Pedido ${selectedOrder.id} no backend` : "Selecione um pedido salvo"}
      </div>
    </Card>
  );
}

function MockUsage() {
  return (
    <Card className="border-transparent bg-ink text-primary-foreground">
      <div className="flex items-center gap-2 text-sm text-primary-foreground/70">
        <Icon name="database" size={16} /> Armazenamento local
      </div>
      <div className="mt-3 flex items-end gap-2">
        <span className="font-mono text-4xl font-semibold">142.6</span>
        <span className="mb-1 text-primary-foreground/60">/ 210 GB</span>
      </div>
      <div className="mt-4 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-accent" style={{ width: "68%" }} />
      </div>
      <div className="mt-4 flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2 text-xs text-primary-foreground/70">
        <Icon name="clock" size={14} className="text-accent" />
        Demo local · conecte a API para upload real
      </div>
    </Card>
  );
}

function MiniStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <Card>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="mt-2 font-display text-3xl font-semibold text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{sub}</div>
    </Card>
  );
}

function OrderSelector({
  orders,
  selectedOrderId,
  onSelect,
}: {
  orders: Order[];
  selectedOrderId: string;
  onSelect: (orderId: string) => void;
}) {
  return (
    <Card className="p-0">
      <div className="border-b border-border px-5 py-4">
        <SectionTitle>Pedidos</SectionTitle>
      </div>
      <div className="max-h-[420px] overflow-y-auto p-2">
        {orders.map((order) => (
          <button
            key={order.id}
            type="button"
            onClick={() => onSelect(order.id)}
            className={cx(
              "flex w-full items-center justify-between gap-3 rounded-2xl px-3 py-3 text-left transition-colors",
              selectedOrderId === order.id ? "bg-primary/10" : "hover:bg-secondary/50",
            )}
          >
            <span>
              <span className="block text-sm font-medium text-foreground">{order.pizzaria}</span>
              <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">{order.id}</span>
            </span>
            <Badge tone={stageTone[order.stage]} dot>
              {order.stage}
            </Badge>
          </button>
        ))}
        {orders.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
            Nenhum pedido cadastrado
          </div>
        )}
      </div>
    </Card>
  );
}

function UploadPanel({
  disabled,
  uploading,
  onUpload,
}: {
  disabled: boolean;
  uploading: boolean;
  onUpload: (file: File, purpose: "logo" | "reference") => void;
}) {
  function chooseFile(purpose: "logo" | "reference") {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (file) onUpload(file, purpose);
    };
  }

  return (
    <Card>
      <SectionTitle>Upload</SectionTitle>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
        <label
          className={cx(
            "flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed px-4 py-3 transition-colors",
            disabled ? "pointer-events-none opacity-50" : "hover:border-primary/50",
          )}
        >
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/svg+xml"
            className="sr-only"
            disabled={disabled}
            onChange={chooseFile("logo")}
          />
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            <Icon name="image" size={16} />
          </span>
          <span>
            <span className="block text-sm font-medium text-foreground">Enviar logo</span>
            <span className="block text-xs text-muted-foreground">Associa ao pedido</span>
          </span>
        </label>
        <label
          className={cx(
            "flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed px-4 py-3 transition-colors",
            disabled ? "pointer-events-none opacity-50" : "hover:border-primary/50",
          )}
        >
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,application/pdf"
            className="sr-only"
            disabled={disabled}
            onChange={chooseFile("reference")}
          />
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-secondary-foreground">
            <Icon name="palette" size={16} />
          </span>
          <span>
            <span className="block text-sm font-medium text-foreground">
              {uploading ? "Enviando..." : "Enviar referência"}
            </span>
            <span className="block text-xs text-muted-foreground">Imagem ou PDF de apoio</span>
          </span>
        </label>
      </div>
    </Card>
  );
}

export function Arquivos() {
  const { backendEnabled, listOrderFiles, orders, uploadOrderAsset } = useAppStore();
  const [selectedOrderId, setSelectedOrderId] = useState(orders[0]?.id ?? "");
  const [files, setFiles] = useState<OrderFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const selectedOrder = useMemo(
    () => orders.find((order) => order.id === selectedOrderId) ?? null,
    [orders, selectedOrderId],
  );
  const mockTotalGb = PSD_FILES.reduce((sum, file) => sum + file.size, 0);
  const largestMockFile = PSD_FILES.reduce(
    (largest, file) => (file.size > largest.size ? file : largest),
    PSD_FILES[0],
  );

  useEffect(() => {
    if (!orders.length) {
      setSelectedOrderId("");
      return;
    }
    if (!orders.some((order) => order.id === selectedOrderId)) {
      setSelectedOrderId(orders[0].id);
    }
  }, [orders, selectedOrderId]);

  useEffect(() => {
    if (!backendEnabled || !selectedOrderId) {
      setFiles([]);
      return;
    }

    let active = true;
    setLoadingFiles(true);
    setError("");
    listOrderFiles(selectedOrderId)
      .then((nextFiles) => {
        if (active) setFiles(nextFiles);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Falha ao carregar arquivos");
      })
      .finally(() => {
        if (active) setLoadingFiles(false);
      });

    return () => {
      active = false;
    };
  }, [backendEnabled, listOrderFiles, selectedOrderId]);

  async function handleUpload(file: File, purpose: "logo" | "reference") {
    if (!selectedOrderId) return;
    setUploading(true);
    setError("");
    try {
      await uploadOrderAsset(selectedOrderId, file, purpose);
      setFiles(await listOrderFiles(selectedOrderId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar arquivo");
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Arquivos"
        subtitle="Upload, storage e downloads internos vinculados ao pedido salvo no backend."
        actions={
          <Badge tone={backendEnabled ? "basil" : "neutral"} dot>
            {backendEnabled ? "Backend ativo" : "Modo local"}
          </Badge>
        }
      />

      {error && (
        <div className="mb-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-medium text-primary">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="lg:col-span-2">
          {backendEnabled ? (
            <BackendUsage fileCount={files.length} selectedOrder={selectedOrder} />
          ) : (
            <MockUsage />
          )}
        </div>
        <MiniStat
          label={backendEnabled ? "Pedidos no funil" : "Arquivos gerados"}
          value={backendEnabled ? String(orders.length) : String(PSD_FILES.length)}
          sub={backendEnabled ? "Sincronizados com a API" : `${mockTotalGb.toFixed(1)} GB em demo local`}
        />
        <MiniStat
          label={backendEnabled ? "Pedido selecionado" : "Maior arquivo"}
          value={backendEnabled ? selectedOrder?.id ?? "—" : `${largestMockFile.size.toFixed(1)} GB`}
          sub={backendEnabled ? selectedOrder?.pizzaria ?? "Sem pedido" : largestMockFile.name}
        />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
        <div className="flex flex-col gap-5">
          <OrderSelector orders={orders} selectedOrderId={selectedOrderId} onSelect={setSelectedOrderId} />
          <UploadPanel
            disabled={!backendEnabled || !selectedOrderId || uploading}
            uploading={uploading}
            onUpload={handleUpload}
          />
        </div>

        <Card className="p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 pt-6">
            <SectionTitle>Arquivos do pedido</SectionTitle>
            <Badge tone="ink">
              <Icon name="lock" size={12} /> Uso interno
            </Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-6 py-3 font-medium">Arquivo</th>
                  <th className="px-4 py-3 font-medium">Pedido</th>
                  <th className="px-4 py-3 font-medium">Tipo</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody>
                {backendEnabled ? (
                  files.map((file) => (
                    <tr
                      key={`${file.kind}:${file.filename}`}
                      className="group border-b border-border/60 transition-colors last:border-0 hover:bg-secondary/40"
                    >
                      <td className="px-6 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 font-mono text-[10px] font-semibold text-primary">
                            {extension(file.filename)}
                          </span>
                          <span className="font-mono text-[13px] text-foreground">{file.filename}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-secondary-foreground">{selectedOrder?.pizzaria ?? "—"}</td>
                      <td className="px-4 py-3.5 text-muted-foreground">{kindLabel(file.kind)}</td>
                      <td className="px-4 py-3.5">
                        <Badge tone={file.exists ? "basil" : "neutral"}>
                          {file.exists ? "Disponível" : "Ausente"}
                        </Badge>
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <a
                          className="inline-grid size-8 place-items-center rounded-full text-secondary-foreground transition-colors hover:bg-secondary hover:text-primary"
                          href={file.downloadUrl}
                          aria-label={`Baixar ${file.filename}`}
                        >
                          <Icon name="download" size={15} />
                        </a>
                      </td>
                    </tr>
                  ))
                ) : (
                  PSD_FILES.map((file) => (
                    <tr
                      key={file.name}
                      className="group border-b border-border/60 transition-colors last:border-0 hover:bg-secondary/40"
                    >
                      <td className="px-6 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 font-mono text-[10px] font-semibold text-primary">
                            PSD
                          </span>
                          <span className="font-mono text-[13px] text-foreground">{file.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-secondary-foreground">{file.client}</td>
                      <td className="px-4 py-3.5 font-mono text-foreground">{file.size.toFixed(1)} GB</td>
                      <td className="px-4 py-3.5">
                        <Badge tone={mockStatusTone[file.status]}>{file.status}</Badge>
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <button
                          className="grid size-8 place-items-center rounded-full text-secondary-foreground transition-colors hover:bg-secondary hover:text-primary"
                          aria-label="Baixar"
                        >
                          <Icon name="download" size={15} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
                {backendEnabled && !loadingFiles && files.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center text-sm text-muted-foreground">
                      Nenhum arquivo associado a este pedido.
                    </td>
                  </tr>
                )}
                {backendEnabled && loadingFiles && (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center text-sm text-muted-foreground">
                      Carregando arquivos...
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
