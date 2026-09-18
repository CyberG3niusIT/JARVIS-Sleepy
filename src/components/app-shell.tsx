import type { ReactNode } from "react";

/**
 * Minimal system shell: status strip, title bar, content column.
 * No product navigation yet — branding foundation only.
 */
export function AppShell({
  title,
  status = "Local",
  children,
}: {
  title: string;
  status?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-surface-sunken/95 backdrop-blur-[2px]">
        <div className="mx-auto flex h-9 w-full max-w-3xl items-center justify-between px-5">
          <span className="label-system">J.A.R.V.I.S</span>
          <span className="flex items-center gap-2 label-system">
            <span className="size-1.5 rounded-full bg-primary" aria-hidden />
            {status}
          </span>
        </div>
        <div className="mx-auto w-full max-w-3xl border-t border-border px-5 py-3">
          <h1 className="text-sm font-medium tracking-tight text-foreground">{title}</h1>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl px-5 py-8">{children}</main>
      <footer className="mx-auto w-full max-w-3xl border-t border-border px-5 py-4">
        <p className="label-system">Brand foundation · v0.1</p>
      </footer>
    </div>
  );
}

export function Section({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-border py-7 first:border-t-0 first:pt-0">
      <h2 className="label-system">{label}</h2>
      {description ? (
        <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

/** Slot awaiting an official brand file — never a stock-font recreation. */
export function AssetSlot({
  name,
  spec,
  ratio = "aspect-[3/1]",
}: {
  name: string;
  spec: string;
  ratio?: string;
}) {
  return (
    <div className="panel p-3">
      <div
        className={`${ratio} flex w-full items-center justify-center rounded-sm border border-dashed border-border-strong bg-surface-sunken`}
      >
        <span className="label-system">Asset slot</span>
      </div>
      <div className="mt-3 flex items-baseline justify-between gap-3">
        <span className="text-sm text-foreground">{name}</span>
        <span className="font-mono text-[11px] text-muted-foreground">{spec}</span>
      </div>
    </div>
  );
}
