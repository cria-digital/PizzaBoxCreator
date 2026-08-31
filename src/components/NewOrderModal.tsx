import { useState } from "react";
import { Modal } from "./ui/Overlay";
import { Icon } from "./ui/Icon";
import { Badge, Button, cx } from "./ui/primitives";
import { useAppStore, type NewOrderInput } from "../store/AppStore";
import type { Order } from "../data";

const steps = ["Dados da pizzaria", "Orientações para a IA", "Confirmação"] as const;

const infoKeys = ["Endereço", "Telefone", "Rede social", "QR Code"] as const;
const infoPlaceholder: Record<string, string> = {
  Endereço: "Rua, número, bairro",
  Telefone: "(00) 00000-0000",
  "Rede social": "@pizzaria",
  "QR Code": "https:// link do cardápio",
};

const boxSizes = ["30 cm", "35 cm", "40 cm", "Múltiplos tamanhos"];

function Label({ children }: { children: string }) {
  return <label className="mb-1.5 block text-sm font-medium text-secondary-foreground">{children}</label>;
}
const inputCls =
  "w-full rounded-2xl border border-border bg-secondary/40 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:bg-card focus:outline-none focus:ring-2 focus:ring-ring/20";

const isHex = (v: string) => /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v);

export function NewOrderModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { createOrder } = useAppStore();
  const [step, setStep] = useState(0);
  const [size, setSize] = useState(boxSizes[1]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [contact, setContact] = useState("");
  const [done, setDone] = useState(false);
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);

  // AI briefing
  const [logo, setLogo] = useState(false);
  const [reference, setReference] = useState(false);
  const [colors, setColors] = useState<string[]>(["#df4526"]);
  const [context, setContext] = useState("");
  const [mustText, setMustText] = useState("");
  const [info, setInfo] = useState<Record<string, { on: boolean; value: string }>>({
    Endereço: { on: true, value: "" },
    Telefone: { on: true, value: "" },
    "Rede social": { on: false, value: "" },
    "QR Code": { on: false, value: "" },
  });

  const setColor = (i: number, v: string) =>
    setColors((prev) => prev.map((c, idx) => (idx === i ? v : c)));
  const addColor = () => setColors((prev) => [...prev, "#e2992d"]);
  const removeColor = (i: number) => setColors((prev) => prev.filter((_, idx) => idx !== i));
  const updateInfo = (k: string, patch: Partial<{ on: boolean; value: string }>) =>
    setInfo((prev) => ({ ...prev, [k]: { ...prev[k], ...patch } }));

  function close() {
    onClose();
    // reset after the close animation
    setTimeout(() => {
      setStep(0);
      setDone(false);
      setName("");
      setPhone("");
      setCity("");
      setContact("");
      setCreatedOrder(null);
    }, 250);
  }

  function submitOrder() {
    const activeInfo = Object.fromEntries(
      infoKeys.map((key) => [key, info[key].on ? info[key].value : ""]),
    ) as Record<(typeof infoKeys)[number], string>;

    const input: NewOrderInput = {
      pizzaria: name || "Nova pizzaria",
      city,
      phone: phone || activeInfo.Telefone,
      contact,
      boxSize: size,
      instagram: activeInfo["Rede social"],
      requiredText: mustText,
      colors,
      context,
      hasLogo: logo,
      hasReference: reference,
    };

    const order = createOrder(input);
    setCreatedOrder(order);
    setDone(true);
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
        <Button onClick={submitOrder}>
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
          <div className="mt-4 font-mono text-xs text-muted-foreground">
            {createdOrder?.id ?? "Pedido criado"}
          </div>
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
                  <input
                    className={inputCls}
                    placeholder="+55 19 90000-0000"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Cidade</Label>
                  <input
                    className={inputCls}
                    placeholder="Campinas, SP"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>Contato responsável</Label>
                <input
                  className={inputCls}
                  placeholder="Nome de quem está falando no WhatsApp"
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                />
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
              <p className="-mt-1 text-sm text-muted-foreground">
                O que a IA deve incluir e respeitar ao montar a arte.
              </p>

              {/* logotipo */}
              <div>
                <Label>Inserção de logotipo</Label>
                <button
                  type="button"
                  onClick={() => setLogo((v) => !v)}
                  className={cx(
                    "flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                    logo ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
                  )}
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-secondary-foreground">
                    <Icon name="image" size={16} />
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-medium text-foreground">
                      {logo ? "Logotipo anexado" : "Anexar logotipo"}
                    </span>
                    <span className="block text-xs text-muted-foreground">PNG ou SVG · fundo transparente</span>
                  </span>
                  {logo && <Icon name="check" size={16} className="text-primary" />}
                </button>
              </div>

              {/* cores — livre com color picker + hex */}
              <div>
                <Label>Cores da arte</Label>
                <div className="flex flex-col gap-2">
                  {colors.map((c, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <label
                        className="relative size-10 shrink-0 overflow-hidden rounded-xl border border-border"
                        style={{ background: isHex(c) ? c : "transparent" }}
                      >
                        <input
                          type="color"
                          value={isHex(c) ? (c.length === 4
                            ? "#" + c.slice(1).split("").map((h) => h + h).join("")
                            : c) : "#df4526"}
                          onChange={(e) => setColor(i, e.target.value)}
                          className="absolute inset-0 size-full cursor-pointer opacity-0"
                          aria-label={`Escolher cor ${i + 1}`}
                        />
                      </label>
                      <input
                        value={c}
                        onChange={(e) => setColor(i, e.target.value)}
                        placeholder="#df4526"
                        spellCheck={false}
                        className={cx(
                          inputCls,
                          "flex-1 font-mono uppercase",
                          !isHex(c) && "border-primary/60 text-primary",
                        )}
                      />
                      {colors.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeColor(i)}
                          className="grid size-9 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                          aria-label="Remover cor"
                        >
                          <Icon name="trash" size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={addColor}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  <Icon name="plus" size={13} /> Adicionar cor
                </button>
              </div>

              {/* contexto livre */}
              <div>
                <Label>Contexto para a IA</Label>
                <textarea
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  rows={3}
                  placeholder="Ex.: forno a lenha desde 1998, clima acolhedor, valorizar a borda recheada…"
                  className={cx(inputCls, "resize-none")}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Somado ao prompt de geração da arte.
                </p>
              </div>

              {/* referência visual */}
              <div>
                <Label>Referência visual</Label>
                <button
                  type="button"
                  onClick={() => setReference((v) => !v)}
                  className={cx(
                    "flex w-full items-center gap-3 rounded-2xl border border-dashed px-4 py-3 text-left transition-colors",
                    reference ? "border-primary bg-primary/5" : "border-border hover:border-primary/40",
                  )}
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-secondary-foreground">
                    <Icon name="palette" size={16} />
                  </span>
                  <span className="flex-1 text-sm">
                    <span className="block font-medium text-foreground">
                      {reference ? "Referência anexada" : "Enviar imagem de referência"}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      Uma arte ou estilo que sirva de inspiração
                    </span>
                  </span>
                  {reference && <Icon name="check" size={16} className="text-primary" />}
                </button>
              </div>

              {/* informações na caixa */}
              <div>
                <Label>Informações impressas na caixa</Label>
                <div className="flex flex-col gap-2">
                  {infoKeys.map((k) => (
                    <div key={k} className="rounded-2xl border border-border p-3">
                      <label className="flex items-center justify-between">
                        <span className="text-sm text-foreground">{k}</span>
                        <span className="relative inline-flex h-6 w-11 cursor-pointer items-center rounded-full bg-muted has-[:checked]:bg-primary">
                          <input
                            type="checkbox"
                            className="peer sr-only"
                            checked={info[k].on}
                            onChange={(e) => updateInfo(k, { on: e.target.checked })}
                          />
                          <span className="absolute left-0.5 size-5 rounded-full bg-card shadow transition-transform peer-checked:translate-x-5" />
                        </span>
                      </label>
                      {info[k].on && (
                        <input
                          value={info[k].value}
                          onChange={(e) => updateInfo(k, { value: e.target.value })}
                          placeholder={infoPlaceholder[k]}
                          className={cx(inputCls, "mt-2 py-2")}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* texto obrigatório */}
              <div>
                <Label>Texto obrigatório na caixa</Label>
                <input
                  value={mustText}
                  onChange={(e) => setMustText(e.target.value)}
                  placeholder="Ex.: Sabor que vem do forno"
                  className={inputCls}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  A IA nunca remove nem altera este texto.
                </p>
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
                  ["Logotipo", logo ? "Anexado" : "Não"],
                  ["Referência", reference ? "Anexada" : "Não"],
                  ["Informações", infoKeys.filter((k) => info[k].on).join(", ") || "—"],
                  ["Texto obrigatório", mustText || "—"],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex items-center justify-between px-4 py-3 text-sm">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="font-medium text-foreground">{v}</dd>
                  </div>
                ))}
                <div className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                  <dt className="text-muted-foreground">Cores</dt>
                  <dd className="flex flex-wrap items-center justify-end gap-1.5">
                    {colors.map((c, i) => (
                      <span key={i} className="inline-flex items-center gap-1 font-mono text-xs text-foreground">
                        <span
                          className="size-4 rounded-full ring-1 ring-black/10"
                          style={{ background: isHex(c) ? c : "transparent" }}
                        />
                        {c.toUpperCase()}
                      </span>
                    ))}
                  </dd>
                </div>
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
