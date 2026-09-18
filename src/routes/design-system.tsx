import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Home, LayoutGrid, MessageSquare, MoreHorizontal } from "lucide-react";
import {
  colorTokens,
  duration,
  easing,
  elevation,
  layout,
  motionRules,
  radii,
  safeArea,
  spacing,
  typeScale,
  zIndex,
} from "@/lib/jarvis/tokens";
import {
  DesignStateBlock,
  Divider,
  ExecutionTag,
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import {
  BottomSheet,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  NotImplementedState,
  PermissionRequiredState,
  TextInput,
  Toggle,
} from "@/components/jarvis/controls";
import { BottomNav, RuntimeStrip, TopAppBar, type NavItem } from "@/components/jarvis/shell";
import { ScreenTransition, useDirection } from "@/components/jarvis/motion";
import { JarvisSymbol, JarvisWordmark } from "@/components/brand/jarvis-mark";
import { Composer } from "@/components/jarvis/blocks";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import { useReducedMotion } from "@/hooks/use-reduced-motion";
import {
  moreDestinations,
  navTabs,
  systemDestinations,
  type ExecutionLocation,
  type PrivacyMode,
  type SystemState,
} from "@/lib/jarvis/ia";

/**
 * Development-only design system reference.
 * Not a product area, not reachable from the JARVIS bottom navigation.
 */
export const Route = createFileRoute("/design-system")({
  head: () => ({
    meta: [
      { title: "Designsystem: J.A.R.V.I.S Mobile" },
      {
        name: "description",
        content:
          "Interne Referenz für Tokens, Bewegung und Komponenten von J.A.R.V.I.S Mobile. Kein Produktbereich.",
      },
      { property: "og:title", content: "Designsystem: J.A.R.V.I.S Mobile" },
      {
        property: "og:description",
        content: "Tokens, Bewegungstokens und gesperrte Komponenten für den lokalen Android-Assistenten.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DesignSystemPage,
});

function DesignSystemPage() {
  const reduced = useReducedMotion();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border-soft px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div>
            <h1 className="text-[15px] font-medium text-foreground">Designsystem</h1>
            <p className="mt-0.5 text-[12px] text-muted-foreground">
              Interne Referenz der freigegebenen UI/UX-Baseline. Kein Produktbereich, nicht in der Navigation.
            </p>
          </div>
          <Link to="/prototypes/shell" className="text-[12px] text-primary">
            J.A.R.V.I.S Mobile Vorschau
          </Link>
        </div>
      </header>

      <main className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-8">
        <p className="value-mono">
          Reduzierte Bewegung: {reduced ? "aktiv, Verschiebungen entfallen" : "nicht aktiv"}
        </p>

        <Block title="Farbe">
          <div className="grid grid-cols-2 gap-px bg-border-soft sm:grid-cols-4">
            {colorTokens.map((c) => (
              <div key={c.name} className="bg-surface p-3">
                <span
                  className="mb-2 block h-8 rounded-xs border border-border-soft"
                  style={{ backgroundColor: c.hex }}
                  aria-hidden
                />
                <span className="block text-[12px] text-foreground">{c.name}</span>
                <span className="value-mono block">{c.hex}</span>
                <span className="mt-1 block text-[11px] text-muted-foreground">{c.use}</span>
              </div>
            ))}
          </div>
        </Block>

        <Block title="Typografie">
          <ListGroup>
            {typeScale.map((t) => (
              <ListRow
                key={t.name}
                title={
                  <span
                    style={{ fontSize: t.px, lineHeight: `${t.lh}px`, fontWeight: t.weight }}
                    className={t.name === "mono" ? "font-mono" : undefined}
                  >
                    {t.use}
                  </span>
                }
                subtitle={`${t.name}, ${t.px}/${t.lh}, Gewicht ${t.weight}`}
              />
            ))}
          </ListGroup>
        </Block>

        <Block title="Abstand, Radius, Raster">
          <div className="grid gap-6 sm:grid-cols-3">
            <Metrics
              label="Abstand (dp)"
              rows={Object.entries(spacing).map(([k, v]) => [k, String(v)])}
            />
            <Metrics
              label="Radius (dp)"
              rows={Object.entries(radii).map(([k, v]) => [k, String(v)])}
            />
            <Metrics
              label="Layout (dp)"
              rows={[
                ["Touchziel min.", String(layout.touchTargetMin)],
                ["Topbar", String(layout.topBarHeight)],
                ["Runtime-Leiste", String(layout.runtimeStripHeight)],
                ["Bottom Nav", String(layout.bottomNavHeight)],
                ["Icon klein/mittel/groß", `${layout.iconSm}/${layout.iconMd}/${layout.iconLg}`],
                ["Safe Area oben/unten", `${safeArea.top}/${safeArea.bottom}`],
              ]}
            />
          </div>
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <Metrics
              label="Ebenen (z-index)"
              rows={Object.entries(zIndex).map(([k, v]) => [k, String(v)])}
            />
            <Metrics
              label="Elevation"
              rows={[
                ["flat", "Nur Haarlinie, kein Schatten"],
                ["raised", elevation.raised],
                ["overlay", elevation.overlay],
              ]}
            />
          </div>
        </Block>

        <Block title="Bewegungstokens">
          <div className="grid gap-6 sm:grid-cols-2">
            <Metrics
              label="Dauer (ms)"
              rows={Object.entries(duration).map(([k, v]) => [k, String(v)])}
            />
            <Metrics label="Easing" rows={Object.entries(easing).map(([k, v]) => [k, v])} />
          </div>
          <ul className="mt-4 flex flex-col gap-1.5">
            {motionRules.map((r) => (
              <li key={r} className="text-[12px] leading-5 text-muted-foreground">
                {r}
              </li>
            ))}
          </ul>
        </Block>

        <Block title="Tags und Status">
          <TagSection />
        </Block>

        <Block title="Buttons">
          <ButtonSection />
        </Block>

        <Block title="Zeilen">
          <ListGroup>
            <ListRow title="Listenzeile" subtitle="48 dp Mindesthöhe" />
            <ListRow
              title="Einstellungszeile"
              subtitle="Mit Schalter"
              trailing={<ToggleDemo />}
            />
            <ListRow
              title="Fähigkeitszeile"
              subtitle="Status und Ausführungsort"
              trailing={
                <span className="flex items-center gap-2">
                  <StatusTag state="permission_required" dot={false} />
                  <ExecutionTag where="LOKAL" />
                </span>
              }
            />
            <ListRow title="Ausgewählte Zeile" selected />
          </ListGroup>
        </Block>

        <Block title="Hinweise und Zustände">
          <div className="grid gap-4 sm:grid-cols-2">
            <InlineNotice>Ausführung bleibt lokal, solange nichts anderes markiert ist.</InlineNotice>
            <InlineNotice tone="warning">
              Sleepy: nicht verbunden. Kein automatischer Handoff.
            </InlineNotice>
            <InlineNotice tone="error">Das Modell konnte nicht geladen werden.</InlineNotice>
            <DesignStateBlock state="design_state" note="Platzhalter statt gemessener Werte." />
            <LoadingState label="Modellindex wird gelesen" />
            <EmptyState />
            <ErrorState />
            <PermissionRequiredState />
            <NotImplementedState />
          </div>
        </Block>

        <Block title="Eingabe und Composer">
          <InputSection />
        </Block>

        <Block title="Overlays">
          <OverlaySection />
        </Block>

        <Block title="Runtime-Leiste">
          <RuntimeStripSection />
        </Block>

        <Block title="Bottom Navigation und Bildschirmwechsel">
          <NavSection />
        </Block>

        <Block title="Informationsarchitektur (festgelegt)">
          <IaSection />
        </Block>

        <Block title="Bildschirmzustände">
          <ScreenStatesSection />
        </Block>

        <Block title="Android-Identität">
          <AndroidIdentitySection />
        </Block>

        <Block title="Android-Systeminteraktion">
          <AndroidSystemInteractionSection />
        </Block>
      </main>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="label-system pb-3">{title}</h2>
      <Divider />
      <div className="pt-4">{children}</div>
    </section>
  );
}

function Metrics({ label, rows }: { label: string; rows: [string, string][] }) {
  return (
    <div>
      <h3 className="label-system pb-2">{label}</h3>
      <dl className="divide-y divide-border-soft border-y border-border-soft">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-4 py-2">
            <dt className="text-[12px] text-subtle-foreground">{k}</dt>
            <dd className="value-mono truncate">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const allStates: SystemState[] = [
  "ready",
  "local",
  "sleepy",
  "waiting_remote",
  "offline",
  "unavailable",
  "permission_required",
  "privacy_blocked",
  "error",
  "not_implemented",
  "degraded",
  "design_state",
];

function TagSection() {
  const executions: ExecutionLocation[] = ["LOKAL", "SLEEPY", "CLOUD", "EXTERN"];
  const modes: PrivacyMode[] = ["NORMAL", "PRIVACY", "PRIVACY_LOCK"];
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {allStates.map((s) => (
          <StatusTag key={s} state={s} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {executions.map((e) => (
          <ExecutionTag key={e} where={e} />
        ))}
      </div>
      <div className="flex flex-wrap gap-5">
        {modes.map((m) => (
          <PrivacyTag key={m} mode={m} />
        ))}
      </div>
      <p className="text-[12px] text-muted-foreground">
        Jeder Zustand trägt Text, nicht nur Farbe. Der Punkt ist zusätzlich, nicht tragend.
      </p>
    </div>
  );
}

function ToggleDemo() {
  const [on, setOn] = useState(false);
  return <Toggle checked={on} onChange={setOn} label="Beispielschalter" />;
}

function ButtonSection() {
  // Local demonstration state only. No product behavior, no runtime call.
  const [lastAction, setLastAction] = useState<string | null>(null);
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={() => setLastAction("Primär ausgelöst")}>
          Lokal ausführen
        </Button>
        <Button variant="secondary" onClick={() => setLastAction("Sekundär ausgelöst")}>
          Abbrechen
        </Button>
        <Button variant="destructive" onClick={() => setLastAction("Destruktiv ausgelöst")}>
          Modell löschen
        </Button>
        <Button disabled>Nicht verfügbar</Button>
      </div>
      <p aria-live="polite" className="mt-3 text-[12px] text-muted-foreground">
        {lastAction ? `Demonstration: ${lastAction}` : "Demonstration: noch keine Auswahl"}
      </p>
      <p className="mt-2 text-[12px] text-muted-foreground">
        Druckfeedback: 80 ms Skalierung und Flächenwechsel, bei reduzierter Bewegung nur Fläche.
      </p>
    </div>
  );
}

function InputSection() {
  const [value, setValue] = useState("");
  return (
    <div className="flex max-w-md flex-col gap-4 border border-border-soft bg-surface py-4">
      <TextInput
        id="ds-input"
        label="Textfeld"
        value={value}
        onChange={setValue}
        placeholder="Name des Modells"
      />
      <Composer />
    </div>
  );
}

function OverlaySection() {
  const [sheet, setSheet] = useState(false);
  const [dialog, setDialog] = useState(false);
  return (
    <div className="relative h-[360px] overflow-hidden rounded-md border border-border bg-surface">
      <div className="flex flex-wrap gap-3 p-4">
        <Button onClick={() => setSheet(true)}>Bottom Sheet öffnen</Button>
        <Button onClick={() => setDialog(true)}>Dialog öffnen</Button>
      </div>
      <BottomSheet open={sheet} onClose={() => setSheet(false)} title="Ausführungsort wählen">
        <ListGroup>
          <ListRow title="Lokal" trailing={<ExecutionTag where="LOKAL" />} onClick={() => setSheet(false)} />
          <ListRow
            title="Sleepy"
            subtitle={comparisonBaseline.labels.sleepy}
            trailing={<StatusTag state="unavailable" dot={false} />}
          />
        </ListGroup>
      </BottomSheet>
      <Dialog
        open={dialog}
        onClose={() => setDialog(false)}
        title="Modell entfernen"
        description="Das lokale Modell wird vom Gerät gelöscht. Die Aktion lässt sich nicht rückgängig machen."
      >
        <Button onClick={() => setDialog(false)}>Abbrechen</Button>
        <Button variant="destructive" onClick={() => setDialog(false)}>
          Entfernen
        </Button>
      </Dialog>
    </div>
  );
}

function RuntimeStripSection() {
  const [alt, setAlt] = useState(false);
  return (
    <div className="flex max-w-md flex-col gap-3">
      <div className="border border-border-soft">
        <RuntimeStrip
          runtimeState={alt ? "offline" : "design_state"}
          runtimeLabel={alt ? "Offline, nur lokale Aktionen" : comparisonBaseline.labels.runtime}
          execution={comparisonBaseline.execution}
          privacy={alt ? "PRIVACY" : comparisonBaseline.privacyMode}
        />
      </div>
      <Button onClick={() => setAlt((v) => !v)}>Zustand wechseln</Button>
      <p className="text-[12px] text-muted-foreground">
        Wertwechsel blenden über, sie blinken nicht. Beide Zustände sind Entwurfszustände.
      </p>
    </div>
  );
}

const demoTabs: NavItem<string>[] = [
  { id: "start", label: "Start", icon: Home },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "system", label: "System", icon: LayoutGrid },
  { id: "more", label: "Mehr", icon: MoreHorizontal },
];

function NavSection() {
  const [tab, setTab] = useState("start");
  const index = demoTabs.findIndex((t) => t.id === tab);
  const direction = useDirection(index);
  const current = demoTabs[index]!;

  return (
    <div className="flex max-w-md flex-col overflow-hidden rounded-md border border-border bg-background">
      <TopAppBar onSettings={() => setTab("more")} />
      <div className="h-40 overflow-hidden">
        <ScreenTransition transitionKey={tab} direction={direction}>
          <SectionHeader>{current.label}</SectionHeader>
          <p className="px-4 text-[12px] leading-5 text-muted-foreground">
            Der Wechsel folgt der Navigationsreihenfolge: nach rechts für spätere Ziele, nach
            links zurück. Bei reduzierter Bewegung bleibt nur die Deckkraft.
          </p>
        </ScreenTransition>
      </div>
      <BottomNav items={demoTabs} current={tab} onSelect={setTab} />
    </div>
  );
}

/** Development-only reference of the locked hierarchy. Not a product area. */
function IaSection() {
  return (
    <div className="flex flex-col gap-6">
      <ListGroup>
        {navTabs.map((t) => (
          <ListRow
            key={t.id}
            title={`${t.order}. ${t.label}`}
            subtitle={t.purpose}
          />
        ))}
      </ListGroup>
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="label-system pb-2">System</h3>
          <ListGroup>
            {systemDestinations.map((a) => (
              <ListRow
                key={a.id}
                title={`${a.order}. ${a.label}`}
                subtitle={a.purpose}
                trailing={<StatusTag state={a.state} dot={false} />}
              />
            ))}
          </ListGroup>
        </div>
        <div>
          <h3 className="label-system pb-2">Mehr</h3>
          <ListGroup>
            {moreDestinations.map((a) => (
              <ListRow
                key={a.id}
                title={`${a.order}. ${a.label}`}
                subtitle={a.purpose}
                trailing={<StatusTag state={a.state} dot={false} />}
              />
            ))}
          </ListGroup>
        </div>
      </div>
      <p className="text-[12px] leading-5 text-muted-foreground">
        Die vier Tabs sind fest. Jedes Ziel hat genau einen Platz, es gibt keine
        Doppelung zwischen System und Mehr. Entfernte Bereiche (Finanzen, Essen und
        Einkauf, Social-Suite, Gemini-Nano-Mock, simulierte Bildschirmaufnahme,
        Browser-Inkognito als Privacy) bleiben ausgeschlossen.
      </p>
    </div>
  );
}
