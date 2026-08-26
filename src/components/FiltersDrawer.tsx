import { useState } from "react";
import { Drawer } from "./ui/Overlay";
import { Button, cx } from "./ui/primitives";
import { STAGES } from "../data";

const cities = ["Campinas", "Valinhos", "Hortolândia", "Sumaré", "Paulínia"];
const revisions = ["Sem ajustes", "1–2 ajustes", "3+ ajustes"];

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-border pb-5">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  );
}

export function FiltersDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [stages, setStages] = useState<string[]>([]);
  const [city, setCity] = useState<string[]>([]);
  const [rev, setRev] = useState<string>("");

  const toggle = (list: string[], set: (v: string[]) => void, v: string) =>
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const clear = () => {
    setStages([]);
    setCity([]);
    setRev("");
  };
  const count = stages.length + city.length + (rev ? 1 : 0);

  const Chip = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      className={cx(
        "rounded-full border px-3.5 py-1.5 text-sm transition-colors",
        active
          ? "border-transparent bg-ink text-primary-foreground"
          : "border-border text-secondary-foreground hover:border-primary/40",
      )}
    >
      {children}
    </button>
  );

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Filtros"
      subtitle="Refine a fila de pedidos"
      footer={
        <>
          <Button variant="ghost" className="flex-1" onClick={clear}>
            Limpar
          </Button>
          <Button className="flex-1" onClick={onClose}>
            Aplicar {count > 0 && `(${count})`}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        <Group title="Etapa do pedido">
          <div className="flex flex-wrap gap-2">
            {STAGES.map((s) => (
              <Chip key={s} active={stages.includes(s)} onClick={() => toggle(stages, setStages, s)}>
                {s}
              </Chip>
            ))}
          </div>
        </Group>

        <Group title="Cidade">
          <div className="flex flex-wrap gap-2">
            {cities.map((c) => (
              <Chip key={c} active={city.includes(c)} onClick={() => toggle(city, setCity, c)}>
                {c}
              </Chip>
            ))}
          </div>
        </Group>

        <Group title="Revisões">
          <div className="flex flex-wrap gap-2">
            {revisions.map((r) => (
              <Chip key={r} active={rev === r} onClick={() => setRev(rev === r ? "" : r)}>
                {r}
              </Chip>
            ))}
          </div>
        </Group>

        <label className="flex items-center justify-between">
          <span className="text-sm text-secondary-foreground">Somente aguardando aprovação</span>
          <span className="relative inline-flex h-6 w-11 cursor-pointer items-center rounded-full bg-muted has-[:checked]:bg-primary">
            <input type="checkbox" className="peer sr-only" />
            <span className="absolute left-0.5 size-5 rounded-full bg-card shadow transition-transform peer-checked:translate-x-5" />
          </span>
        </label>
      </div>
    </Drawer>
  );
}
