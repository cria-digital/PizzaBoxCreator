import { useState } from "react";
import { Modal } from "./ui/Overlay";
import { Icon } from "./ui/Icon";
import { Badge, Button, cx } from "./ui/primitives";

const steps = ["Dados da pizzaria", "Preferências visuais", "Confirmação"] as const;

const boxSizes = ["30 cm", "35 cm", "40 cm", "Múltiplos tamanhos"];
const moods = ["Clássica italiana", "Moderna / minimalista", "Rústica / forno a lenha", "Divertida / colorida"];
const palettes = [
  { label: "Tomate & manjericão", colors: ["#df4526", "#4f7a3a", "#fff6ef"] },
  { label: "Forno & brasa", colors: ["#2a211a", "#df4526", "#e2992d"] },
  { label: "Kraft artesanal", colors: ["#c69a6d", "#7a6a54", "#2a211a"] },
  { label: "Moderna clean", colors: ["#1c1c1c", "#df4526", "#f4ecdc"] },
];

function Label({ children }: { children: string }) {
  return <label className="mb-1.5 block text-sm font-medium text-secondary-foreground">{children}</label>;
}
const inputCls =
  "w-full rounded-2xl border border-border bg-secondary/40 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:bg-card focus:outline-none focus:ring-2 focus:ring-ring/20";

export function NewOrderModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(0);
  const [size, setSize] = useState(boxSizes[1]);
  const [mood, setMood] = useState(moods[0]);
  const [palette, setPalette] = useState(0);
  const [name, setName] = useState("");
  const [done, setDone] = useState(false);

  function close() {
    onClose();
    // reset after the close animation
    setTimeout(() => {
      setStep(0);
      setDone(false);
      setName("");
    }, 250);
  }

  const footer = done ? (
    <Button onClick={close}>Concluir</Button>
  ) : (
    <>
      {step > 0 && (
        <Button variant="ghost" onClick={() => setStep((s) => s - 1)}>
          Voltar
        </Button>
      )}
      {step < steps.length - 1 ? (
        <Button onClick={() => setStep((s) => s + 1)}>
          Continuar <Icon name="chevronRight" size={16} />
        </Button>
      ) : (
        <Button onClick={() => setDone(true)}>
          <Icon name="chat" size={16} /> Criar e abrir no WhatsApp
        </Button>
      )}
    </>
  );

  return (
    <Modal
      open={open}
      onClose={close}
      title={done ? "Pedido criado" : "Novo pedido"}
      subtitle={done ? undefined : `Etapa ${step + 1} de ${steps.length} · ${steps[step]}`}
      footer={footer}
    >
      {done ? (
        <div className="flex flex-col items-center py-6 text-center">
          <span className="grid size-16 place-items-center rounded-full bg-[#4f7a3a]/12 text-[#4f7a3a]">
            <Icon name="check" size={32} />
          </span>
          <h3 className="mt-4 font-display text-2xl font-semibold text-foreground">
            {name || "Nova pizzaria"} está na fila
          </h3>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            Um atendimento automático foi disparado no WhatsApp para coletar logo, endereço e sabores.
            O pedido entra na etapa <strong className="text-foreground">Coleta de dados</strong>.
          </p>
          <div className="mt-4 font-mono text-xs text-muted-foreground">PBX-2419</div>
        </div>
      ) : (
        <>
          {/* progress bar */}
          <div className="mb-6 flex gap-1.5">
            {steps.map((_, i) => (
              <div
                key={i}
                className={cx(
                  "h-1.5 flex-1 rounded-full transition-colors",
                  i <= step ? "bg-primary" : "bg-muted",
                )}
              />
            ))}
          </div>

          {step === 0 && (
            <div className="flex flex-col gap-4">
              <div>
                <Label>Nome da pizzaria</Label>
                <input
                  className={inputCls}
                  placeholder="ex. Forno di Napoli"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>WhatsApp</Label>
                  <input className={inputCls} placeholder="+55 19 90000-0000" />
                </div>
                <div>
                  <Label>Cidade</Label>
                  <input className={inputCls} placeholder="Campinas, SP" />
                </div>
              </div>
              <div>
                <Label>Tamanho da caixa</Label>
                <div className="flex flex-wrap gap-2">
                  {boxSizes.map((b) => (
                    <button
                      key={b}
                      onClick={() => setSize(b)}
                      className={cx(
                        "rounded-full border px-4 py-1.5 text-sm transition-colors",
                        size === b
                          ? "border-transparent bg-ink text-primary-foreground"
                          : "border-border text-secondary-foreground hover:border-primary/40",
                      )}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="flex flex-col gap-5">
              <div>
                <Label>Estilo visual</Label>
                <div className="grid grid-cols-2 gap-2">
                  {moods.map((m) => (
                    <button
                      key={m}
                      onClick={() => setMood(m)}
                      className={cx(
                        "rounded-2xl border px-4 py-3 text-left text-sm transition-colors",
                        mood === m
                          ? "border-primary bg-primary/5 text-foreground"
                          : "border-border text-secondary-foreground hover:border-primary/40",
                      )}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <Label>Paleta de cores</Label>
                <div className="flex flex-col gap-2">
                  {palettes.map((p, i) => (
                    <button
                      key={p.label}
                      onClick={() => setPalette(i)}
                      className={cx(
                        "flex items-center gap-3 rounded-2xl border px-4 py-2.5 text-sm transition-colors",
                        palette === i
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/40",
                      )}
                    >
                      <span className="flex">
                        {p.colors.map((c) => (
                          <span
                            key={c}
                            className="size-5 rounded-full ring-2 ring-card first:ml-0 [&:not(:first-child)]:-ml-1.5"
                            style={{ background: c }}
                          />
                        ))}
                      </span>
                      <span className="text-foreground">{p.label}</span>
                      {palette === i && <Icon name="check" size={16} className="ml-auto text-primary" />}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Confira o resumo. A IA gera o primeiro preview com marca d'água em seguida.
              </p>
              <dl className="divide-y divide-border overflow-hidden rounded-2xl border border-border">
                {[
                  ["Pizzaria", name || "—"],
                  ["Tamanho da caixa", size],
                  ["Estilo visual", mood],
                  ["Paleta", palettes[palette].label],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between px-4 py-3 text-sm">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="font-medium text-foreground">{v}</dd>
                  </div>
                ))}
              </dl>
              <Badge tone="sauce" dot className="w-fit">
                Preview com marca d'água será gerado pela IA
              </Badge>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
