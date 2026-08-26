import type { ButtonHTMLAttributes, ElementType, ReactNode } from "react";

/* ---------- utility ---------- */
export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/* ---------- Button ---------- */
type Variant = "primary" | "outline" | "ghost" | "dark";
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  children: ReactNode;
}
const buttonVariants: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-foreground hover:brightness-105 shadow-[0_6px_20px_-8px_var(--primary)]",
  outline:
    "border border-border bg-card text-foreground hover:border-primary/50 hover:text-primary",
  ghost: "text-muted-foreground hover:bg-secondary hover:text-foreground",
  dark: "bg-ink text-primary-foreground hover:brightness-125",
};
export function Button({ variant = "primary", className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-50",
        buttonVariants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

/* ---------- Card ---------- */
interface CardProps {
  children: ReactNode;
  className?: string;
  as?: ElementType;
}
export function Card({ children, className, as: Tag = "div" }: CardProps) {
  return (
    <Tag
      className={cx(
        "rounded-[var(--radius)] border border-border/70 bg-card p-6 shadow-[0_1px_2px_rgba(42,33,26,0.04),0_18px_40px_-32px_rgba(42,33,26,0.35)]",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/* ---------- Badge ---------- */
export type Tone = "sauce" | "cheese" | "basil" | "neutral" | "ink";
const badgeTones: Record<Tone, string> = {
  sauce: "bg-primary/10 text-primary",
  cheese: "bg-accent/15 text-[#9c6a12]",
  basil: "bg-[#4f7a3a]/12 text-[#3c5f2c]",
  neutral: "bg-secondary text-secondary-foreground",
  ink: "bg-ink text-primary-foreground",
};
export function Badge({
  children,
  tone = "neutral",
  dot,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium tracking-tight",
        badgeTones[tone],
        className,
      )}
    >
      {dot && <span className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/* ---------- Avatar (initials) ---------- */
const avatarColors = [
  "bg-[#df4526]",
  "bg-[#e2992d]",
  "bg-[#4f7a3a]",
  "bg-[#b8532f]",
  "bg-[#7a6a54]",
];
export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
  const color = avatarColors[name.charCodeAt(0) % avatarColors.length];
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-medium text-white ring-2 ring-card",
        color,
      )}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
    >
      {initials}
    </span>
  );
}

/* ---------- SectionTitle ---------- */
export function SectionTitle({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-5 flex items-center justify-between gap-4">
      <h3 className="font-display text-lg font-semibold text-foreground">{children}</h3>
      {action}
    </div>
  );
}

/* ---------- ProgressRing (semicircle gauge) ---------- */
export function Gauge({ value, label }: { value: number; label: string }) {
  const r = 78;
  const c = Math.PI * r;
  const offset = c * (1 - value / 100);
  return (
    <div className="relative mx-auto w-[260px]">
      <svg viewBox="0 0 200 120" className="w-full">
        <path
          d="M18 108 A82 82 0 0 1 182 108"
          fill="none"
          stroke="var(--muted)"
          strokeWidth={20}
          strokeLinecap="round"
        />
        <path
          d="M18 108 A82 82 0 0 1 182 108"
          fill="none"
          stroke="var(--primary)"
          strokeWidth={20}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.22,1,.36,1)" }}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 px-8 text-center">
        <div className="font-display text-4xl font-semibold leading-none text-foreground">
          {value}%
        </div>
        <div className="mx-auto mt-1.5 max-w-[180px] text-xs leading-snug text-muted-foreground">
          {label}
        </div>
      </div>
    </div>
  );
}
