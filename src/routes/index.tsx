import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { JarvisWordmark, JarvisSymbol } from "@/components/brand/jarvis-mark";
import {
  areasInGroup,
  capabilityRows,
  navTabs,
  type CapabilityDecision,
} from "@/lib/jarvis/ia";
import { StatusTag, ExecutionTag } from "@/components/jarvis/primitives";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Informationsarchitektur: J.A.R.V.I.S Mobile" },
      {
        name: "description",
        content:
          "Festgelegte Informationsarchitektur für J.A.R.V.I.S Mobile, die lokale Android-Runtime.",
      },
      { property: "og:title", content: "Informationsarchitektur: J.A.R.V.I.S Mobile" },
      {
        property: "og:description",
        content: "Navigation, Zieleordnung und Zustandssprache für die lokale Android-Runtime.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PhaseOverview,
});

const decisionTone: Record<CapabilityDecision, string> = {
  KEEP: "text-success",
  MODIFY: "text-subtle-foreground",
  REPLACE: "text-warning",
  NEW: "text-primary",
};

function PhaseOverview() {
  const groups = [
    {
      group: "system" as const,
      label: "System",
      note: "Technisches Kontrollzentrum, feste Reihenfolge",
    },
    {
      group: "more" as const,
      label: "Mehr",
      note: "Sekundäre Nutzerbereiche und Produkteinstellungen",
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border-soft">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <span className="flex items-center gap-3">
            <JarvisSymbol size={18} />
            <JarvisWordmark height={12} />
          </span>
          <span className="value-mono">UI/UX-Baseline</span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        <section>
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Entwicklungs- und Referenzseite, nicht die Produktoberfläche
          </p>
          <p className="mt-3 text-[13px] leading-6 text-subtle-foreground">
            J.A.R.V.I.S Mobile ist die eigenständige lokale Android-Runtime. Sleepy ist
            eine optionale vertraute Laufzeit für begrenzte Handoffs, keine Voraussetzung.
            Die Bottom Navigation ist festgelegt: Start, Chat, System, Mehr. Jedes Ziel
            hat genau einen Platz in dieser Struktur.
          </p>
          <p className="mt-4 text-[13px] font-medium tracking-wide text-primary">
            UNSCHEINBAR. ÜBERLEGEN. MEINS.
          </p>
          <Link
            to="/prototypes/shell"
            className="mt-6 inline-flex h-11 items-center gap-2 rounded-sm border border-primary/50 px-4 text-[13px] text-primary"
          >
            J.A.R.V.I.S Mobile öffnen
            <ArrowRight className="size-4" aria-hidden />
          </Link>
        </section>

        <section className="mt-10">
          <h2 className="label-system">Bottom Navigation</h2>
          <p className="mt-1 text-[11px] text-muted-foreground">Fest, nicht erweiterbar</p>
          <div className="mt-3 divide-y divide-border-soft border-y border-border-soft">
            {navTabs.map((t) => (
              <div key={t.id} className="flex items-start gap-4 py-2.5">
                <span className="w-32 shrink-0 text-[13px] text-foreground">
                  {t.order}. {t.label}
                </span>
                <span className="flex-1 text-[12px] leading-5 text-muted-foreground">
                  {t.purpose}
                </span>
              </div>
            ))}
          </div>
        </section>

        {groups.map((g) => (
          <section key={g.group} className="mt-10">
            <h2 className="label-system">{g.label}</h2>
            <p className="mt-1 text-[11px] text-muted-foreground">{g.note}</p>
            <div className="mt-3 divide-y divide-border-soft border-y border-border-soft">
              {areasInGroup(g.group).map((a) => (
                <div key={a.id} className="flex items-start gap-4 py-2.5">
                  <span className="w-32 shrink-0 text-[13px] text-foreground">
                    {a.order}. {a.label}
                  </span>
                  <span className="flex-1 text-[12px] leading-5 text-muted-foreground">
                    {a.purpose}
                  </span>
                  <span className={`value-mono w-16 shrink-0 text-right ${decisionTone[a.decision]}`}>
                    {a.decision}
                  </span>
                </div>
              ))}
            </div>
          </section>
        ))}

        <section className="mt-10">
          <h2 className="label-system">Fähigkeiten und Ausführungsort</h2>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Entwurfszustände aus dem Capability-Audit. Keine gemessenen Werte.
          </p>
          <div className="mt-3 divide-y divide-border-soft border-y border-border-soft">
            {capabilityRows.map((c) => (
              <div key={c.name} className="flex items-center gap-4 py-2.5">
                <span className="flex-1 text-[13px] text-foreground">{c.name}</span>
                <StatusTag state={c.state} dot={false} />
                <ExecutionTag where={c.execution} />
              </div>
            ))}
          </div>
        </section>

        <p className="mt-10 border-t border-border-soft pt-4 text-[11px] leading-4 text-muted-foreground">
          Entfernt und bewusst nicht in der Navigation: Finanzen, Essen und Einkauf,
          Social-Management-Suite, Gemini-Nano-Mock, simulierte Bildschirmaufnahme.
        </p>
      </main>
    </div>
  );
}
