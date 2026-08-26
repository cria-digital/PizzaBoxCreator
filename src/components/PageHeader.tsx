import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground sm:text-[2.6rem] sm:leading-[1.05]">
          {title}
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">{subtitle}</p>
      </div>
      {actions && (
        <div className="flex flex-wrap items-center justify-end gap-3">{actions}</div>
      )}
    </div>
  );
}
