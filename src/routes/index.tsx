import { createFileRoute } from "@tanstack/react-router";
import { AppShell, AssetSlot, Section } from "@/components/app-shell";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Brand Reference — J.A.R.V.I.S" },
      {
        name: "description",
        content:
          "Brand reference for J.A.R.V.I.S, a local-first AI assistant: color, type, surfaces and asset slots.",
      },
      { property: "og:title", content: "Brand Reference — J.A.R.V.I.S" },
      {
        property: "og:description",
        content: "Color, typography, surfaces and official asset slots for J.A.R.V.I.S.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: BrandReference,
});

const colors = [
  { name: "background", token: "--background", className: "bg-background" },
  { name: "surface", token: "--surface", className: "bg-surface" },
  { name: "surface raised", token: "--surface-raised", className: "bg-surface-raised" },
  { name: "foreground", token: "--foreground", className: "bg-foreground" },
  { name: "muted fg", token: "--muted-foreground", className: "bg-muted-foreground" },
  { name: "primary", token: "--primary", className: "bg-primary" },
  { name: "primary dim", token: "--primary-dim", className: "bg-primary-dim" },
  { name: "success", token: "--success", className: "bg-success" },
  { name: "warning", token: "--warning", className: "bg-warning" },
  { name: "destructive", token: "--destructive", className: "bg-destructive" },
];

const typeScale = [
  { name: "Display", cls: "text-2xl font-semibold tracking-tight", sample: "J.A.R.V.I.S" },
  { name: "Title", cls: "text-base font-medium", sample: "Local AI Assistant" },
  { name: "Body", cls: "text-sm text-muted-foreground", sample: "Runs on device. Answers stay here." },
  { name: "Label", cls: "label-system", sample: "System status" },
  { name: "Mono", cls: "font-mono text-xs text-muted-foreground", sample: "node.local · 12 ms" },
];

function BrandReference() {
  return (
    <AppShell title="Brand Reference">
      <Section
        label="Identity"
        description="Product name, subtitle and claim. Fixed wording — do not paraphrase."
      >
        <div className="panel p-5">
          <p className="text-2xl font-semibold tracking-tight text-foreground">J.A.R.V.I.S</p>
          <p className="mt-1 text-sm text-muted-foreground">Local AI Assistant</p>
          <p className="mt-4 border-t border-border pt-4 text-sm font-medium tracking-wide text-primary">
            UNSCHEINBAR. ÜBERLEGEN. MEINS.
          </p>
        </div>
      </Section>

      <Section
        label="Official assets"
        description="The J.A.R.V.I.S wordmark is a custom brand asset. These slots stay empty until the official files are supplied — no stock-font recreation."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <AssetSlot name="Wordmark" spec="SVG · horizontal" />
          <AssetSlot name="App icon / node mark" spec="SVG · 1:1" ratio="aspect-square" />
          <AssetSlot name="Wordmark, monochrome" spec="SVG · on dark" />
          <AssetSlot name="Adaptive icon layers" spec="PNG · 432 px" ratio="aspect-square" />
        </div>
      </Section>

      <Section
        label="Color"
        description="Graphite and anthracite surfaces with cool gray type. JARVIS blue is reserved for active states, system nodes, focus rings and status."
      >
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-5">
          {colors.map((c) => (
            <div key={c.token} className="bg-surface p-3">
              <div className={`h-10 rounded-sm border border-border ${c.className}`} />
              <p className="mt-2 text-xs text-foreground">{c.name}</p>
              <p className="font-mono text-[10px] text-muted-foreground">{c.token}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section label="Typography" description="Inter for all UI. Mono only for technical values.">
        <div className="panel divide-y divide-border">
          {typeScale.map((t) => (
            <div key={t.name} className="flex items-baseline justify-between gap-6 px-4 py-3">
              <span className={t.cls}>{t.sample}</span>
              <span className="font-mono text-[10px] text-muted-foreground">{t.name}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section
        label="Surfaces & dividers"
        description="Restrained radii, fine 1 px dividers, flat elevation. No glass, no glow."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { name: "sunken", token: "--surface-sunken", cls: "bg-surface-sunken" },
            { name: "base", token: "--surface", cls: "bg-surface" },
            { name: "raised", token: "--surface-raised", cls: "bg-surface-raised" },
          ].map((s) => (
            <div key={s.token} className={`rounded-md border border-border p-4 ${s.cls}`}>
              <p className="text-sm text-foreground">{s.name}</p>
              <p className="mt-1 font-mono text-[10px] text-muted-foreground">{s.token}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        label="States"
        description="Blue appears only where the system is active, focused or reporting."
      >
        <div className="panel divide-y divide-border">
          {[
            { label: "Idle", dot: "bg-muted-foreground", value: "standby" },
            { label: "Active", dot: "bg-primary", value: "listening" },
            { label: "Healthy", dot: "bg-success", value: "model loaded" },
            { label: "Attention", dot: "bg-warning", value: "storage low" },
            { label: "Fault", dot: "bg-destructive", value: "node offline" },
          ].map((s) => (
            <div key={s.label} className="flex items-center justify-between px-4 py-2.5">
              <span className="flex items-center gap-2.5 text-sm text-foreground">
                <span className={`size-1.5 rounded-full ${s.dot}`} aria-hidden />
                {s.label}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{s.value}</span>
            </div>
          ))}
        </div>
      </Section>
    </AppShell>
  );
}
