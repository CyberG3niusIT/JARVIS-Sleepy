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
import { cn } from "@/lib/utils";
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

/* ============================================================
 * Bildschirmzustände (internal reference, development-only)
 * ============================================================ */

type ScreenStateKey =
  | "loading"
  | "ready"
  | "empty"
  | "offline"
  | "error"
  | "permission_required"
  | "privacy_blocked"
  | "runtime_unavailable"
  | "not_implemented";

const screenStateOrder: ScreenStateKey[] = [
  "loading",
  "ready",
  "empty",
  "offline",
  "error",
  "permission_required",
  "privacy_blocked",
  "runtime_unavailable",
  "not_implemented",
];

const screenStateLabel: Record<ScreenStateKey, string> = {
  loading: "Loading",
  ready: "Ready",
  empty: "Empty",
  offline: "Offline",
  error: "Fehler",
  permission_required: "Berechtigung erforderlich",
  privacy_blocked: "Privacy blockiert",
  runtime_unavailable: "Runtime nicht verfügbar",
  not_implemented: "Nicht implementiert",
};

type MatrixMark = "spec" | "baseline" | "na";

const matrixLabel: Record<MatrixMark, string> = {
  spec: "spezifiziert",
  baseline: "Baseline",
  na: "n/v",
};

const matrixSymbol: Record<MatrixMark, string> = {
  spec: "S",
  baseline: "B",
  na: "-",
};

const matrixTone: Record<MatrixMark, string> = {
  spec: "text-primary",
  baseline: "text-success",
  na: "text-disabled",
};

type ScreenFamily = {
  name: string;
  cells: Record<ScreenStateKey, MatrixMark>;
};

const screenFamilies: ScreenFamily[] = [
  {
    name: "Chat",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "spec",
      offline: "spec",
      error: "spec",
      permission_required: "na",
      privacy_blocked: "spec",
      runtime_unavailable: "spec",
      not_implemented: "na",
    },
  },
  {
    name: "Modelle",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "spec",
      offline: "spec",
      error: "spec",
      permission_required: "na",
      privacy_blocked: "na",
      runtime_unavailable: "spec",
      not_implemented: "na",
    },
  },
  {
    name: "Agenten",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "spec",
      offline: "na",
      error: "spec",
      permission_required: "spec",
      privacy_blocked: "spec",
      runtime_unavailable: "spec",
      not_implemented: "spec",
    },
  },
  {
    name: "Berechtigungen",
    cells: {
      loading: "na",
      ready: "baseline",
      empty: "na",
      offline: "na",
      error: "spec",
      permission_required: "spec",
      privacy_blocked: "na",
      runtime_unavailable: "na",
      not_implemented: "na",
    },
  },
  {
    name: "Voice",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "na",
      offline: "spec",
      error: "spec",
      permission_required: "spec",
      privacy_blocked: "spec",
      runtime_unavailable: "spec",
      not_implemented: "spec",
    },
  },
  {
    name: "Memory",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "spec",
      offline: "na",
      error: "spec",
      permission_required: "na",
      privacy_blocked: "spec",
      runtime_unavailable: "na",
      not_implemented: "na",
    },
  },
  {
    name: "Automationen",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "spec",
      offline: "na",
      error: "spec",
      permission_required: "spec",
      privacy_blocked: "na",
      runtime_unavailable: "spec",
      not_implemented: "spec",
    },
  },
  {
    name: "Runtimes",
    cells: {
      loading: "spec",
      ready: "baseline",
      empty: "na",
      offline: "spec",
      error: "spec",
      permission_required: "na",
      privacy_blocked: "na",
      runtime_unavailable: "baseline",
      not_implemented: "na",
    },
  },
];

/**
 * Reusable state pattern documentation. Each pattern maps to one Compose
 * state composable; the matrix below records which screen families use it.
 * Development-only reference, not a product area.
 */
function ScreenStatesSection() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h3 className="label-system pb-2">Zustandsmuster</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <LabeledPattern label="Loading">
            <LoadingState label="Wird geladen" />
          </LabeledPattern>
          <LabeledPattern label="Ready">
            <div className="flex flex-col gap-1.5 px-4 py-4">
              <StatusTag state="ready" />
              <p className="text-[11px] leading-4 text-muted-foreground">
                Inhalt ist vollständig geladen und zeigt echte oder klar markierte
                Entwurfswerte, nie einen unbestimmten Zwischenstand.
              </p>
            </div>
          </LabeledPattern>
          <LabeledPattern label="Empty">
            <EmptyState />
          </LabeledPattern>
          <LabeledPattern label="Offline">
            <DesignStateBlock
              state="offline"
              note="Keine Verbindung zur Gegenstelle. Lokale Aktionen bleiben möglich, alles andere ist sichtbar gesperrt."
            />
          </LabeledPattern>
          <LabeledPattern label="Fehler">
            <ErrorState />
          </LabeledPattern>
          <LabeledPattern label="Berechtigung erforderlich">
            <PermissionRequiredState />
          </LabeledPattern>
          <LabeledPattern label="Privacy blockiert">
            <DesignStateBlock
              state="privacy_blocked"
              note="Privacy-Modus unterbindet die Aktion aktiv. Der Grund steht im Text, kein stiller Ausfall."
            />
          </LabeledPattern>
          <LabeledPattern label="Runtime nicht verfügbar">
            <DesignStateBlock
              state="unavailable"
              note="Die benötigte Laufzeit (z. B. Sleepy) ist nicht erreichbar. Kein automatischer Wechsel auf Cloud."
            />
          </LabeledPattern>
          <LabeledPattern label="Nicht implementiert">
            <NotImplementedState />
          </LabeledPattern>
        </div>
      </div>

      <div>
        <h3 className="label-system pb-2">Zustandsmatrix nach Bildschirmfamilie</h3>
        <div className="overflow-x-auto border border-border-soft">
          <table className="w-full min-w-[720px] border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-border-soft bg-surface">
                <th scope="col" className="px-3 py-2 text-left font-medium text-subtle-foreground">
                  Bildschirmfamilie
                </th>
                {screenStateOrder.map((s) => (
                  <th
                    key={s}
                    scope="col"
                    className="px-2 py-2 text-left font-medium whitespace-nowrap text-subtle-foreground"
                  >
                    {screenStateLabel[s]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-soft">
              {screenFamilies.map((f) => (
                <tr key={f.name}>
                  <th scope="row" className="px-3 py-2 text-left font-normal text-foreground">
                    {f.name}
                  </th>
                  {screenStateOrder.map((s) => {
                    const mark = f.cells[s];
                    return (
                      <td key={s} className="px-2 py-2">
                        <span
                          className={cn("value-mono", matrixTone[mark])}
                          title={matrixLabel[mark]}
                        >
                          {matrixSymbol[mark]}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
          S = spezifiziert (Muster festgelegt, Umsetzung offen), B = wahrheitsgetreue
          Baseline (Zustand ist der aktuell dargestellte Normalfall), - = nicht
          anwendbar für diese Bildschirmfamilie.
        </p>
      </div>
    </div>
  );
}

function LabeledPattern({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border border-border-soft bg-surface">
      <div className="border-b border-border-soft px-3 py-1.5">
        <span className="text-[11px] text-subtle-foreground">{label}</span>
      </div>
      {children}
    </div>
  );
}

/* ============================================================
 * Android-Identität (internal visual spec, existing assets only)
 * ============================================================ */

/**
 * Internal composition guidance for the Android launcher/notification
 * identity. Built entirely from the approved symbol/wordmark PNGs and CSS.
 * No new artwork, no Android project files.
 */
function AndroidIdentitySection() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h3 className="label-system pb-2">Adaptives Launcher-Icon</h3>
        <div className="flex flex-wrap items-start gap-6">
          <div className="flex flex-col items-center gap-2">
            <div className="relative size-24 overflow-hidden rounded-md bg-surface-raised">
              <div className="absolute inset-0 bg-background" aria-hidden />
              <div
                className="absolute inset-[8px] rounded-full border border-dashed border-primary/50"
                aria-hidden
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <JarvisSymbol size={40} />
              </div>
            </div>
            <span className="text-[11px] text-muted-foreground">108 x 108 dp Vollfläche</span>
          </div>
          <dl className="flex max-w-sm flex-col gap-2 text-[12px] leading-5 text-muted-foreground">
            <div>
              <dt className="text-foreground">Safe Zone</dt>
              <dd>
                Symbol bleibt innerhalb des inneren 66 dp Kreises (gestrichelte Linie).
                Adaptive Masken (Kreis, Rund-Quadrat, Squircle) dürfen nichts vom Symbol
                abschneiden.
              </dd>
            </div>
            <div>
              <dt className="text-foreground">Vordergrund/Hintergrund-Trennung</dt>
              <dd>
                Hintergrund ist eine flache Fläche in Markenfarbe (background layer),
                das Symbol liegt als eigene Vordergrundebene (foreground layer)
                zentriert darüber, ohne eigenen Schatten.
              </dd>
            </div>
            <div>
              <dt className="text-foreground">Innenabstand</dt>
              <dd>
                Mindestens 21 dp Abstand zwischen Symbolrand und Kachelrand auf jeder
                Seite, damit Launcher-Parallax das Symbol nicht anschneidet.
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div>
        <h3 className="label-system pb-2">Monochrome Variante (Themed Icon)</h3>
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex size-16 items-center justify-center rounded-full bg-foreground/90">
            <JarvisSymbol size={30} className="brightness-0 invert" />
          </div>
          <p className="max-w-sm text-[12px] leading-5 text-muted-foreground">
            Für themenfähige Launcher-Icons (Android 13+) liefert das Symbol eine
            einfarbige Silhouette ohne Farbverlauf. Das System färbt die Fläche mit der
            Systemfarbe ein, das Symbol selbst bleibt Alphamaske, kein separates Icon.
          </p>
        </div>
      </div>

      <div>
        <h3 className="label-system pb-2">Splash- und Startbildschirm</h3>
        <div className="flex flex-wrap items-start gap-6">
          <div className="flex h-40 w-24 flex-col items-center justify-center gap-2 rounded-md border border-border-soft bg-background">
            <JarvisSymbol size={28} />
            <JarvisWordmark height={10} />
          </div>
          <p className="max-w-sm text-[12px] leading-5 text-muted-foreground">
            Symbol und Wortmarke bleiben vertikal zentriert gestapelt, feste
            Abstände (8 dp) statt gemessener Ladezeit. Kein Fortschrittstext, kein
            zusätzliches Motiv. Der Splash verschwindet mit einer Überblendung,
            sobald Ready erreicht ist.
          </p>
        </div>
      </div>

      <div>
        <h3 className="label-system pb-2">Benachrichtigungssymbol</h3>
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex size-9 items-center justify-center rounded-sm bg-foreground/90">
            <JarvisSymbol size={16} className="brightness-0 invert" />
          </div>
          <p className="max-w-sm text-[12px] leading-5 text-muted-foreground">
            Statusleisten-Icon (24 dp Zielraster) ist eine reine Umriss-Silhouette,
            vollflächig weiß auf transparent, ohne Farbe und ohne Verlauf, wie es das
            Android-System für Benachrichtigungssymbole verlangt.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
 * Android-Systeminteraktion (behaviour reference, no runtime claims)
 * ============================================================ */

const backMappingRows: [string, string][] = [
  ["Start (Tab-Wurzel)", "Zurück verlässt die App (System-Standard), kein Doppel-Tap-Trick."],
  ["Chat, Modelle, Agenten, Voice, Memory (Tab-Wurzeln)", "Zurück springt zum zuletzt aktiven Tab \"Start\", nicht zur App-Historie."],
  ["Detailbildschirm innerhalb eines Tabs", "Zurück geht genau eine Ebene in der Tab-eigenen Historie zurück."],
  ["Bottom Sheet", "Zurück schließt das Sheet, öffnet keine tiefere Navigation."],
  ["Dialog", "Zurück verhält sich wie Abbrechen, außer bei destruktiver Bestätigung ohne Abbrechen-Option."],
  ["Editor mit ungesicherter Eingabe", "Zurück zeigt zuerst einen Bestätigungsdialog (Verwerfen/Weiter bearbeiten)."],
];

const systemInteractionRows: [string, string][] = [
  [
    "Tastatur/IME-Insets",
    "Composer und Formularfelder verschieben sich über den sichtbaren Fensterausschnitt (WindowInsets), Inhalte werden nie von der Tastatur verdeckt, keine feste Pixelannahme.",
  ],
  [
    "Berechtigungsanfrage",
    "Anfrage öffnet den nativen Android-Berechtigungsdialog. Vor dem ersten Systemdialog steht ein eigener Erklärungsschritt (Rationale), danach kein wiederholtes Anfragen ohne neue Nutzeraktion.",
  ],
  [
    "Weiterleitung zu Systemeinstellungen",
    "Bei dauerhaft verweigerter Berechtigung führt eine Zeile direkt in die App-Detailseite der Android-Einstellungen, mit Hinweistext davor, kein automatischer Sprung ohne Bestätigung.",
  ],
  [
    "Foreground-Service-Benachrichtigung",
    "Läuft eine Aktion als Vordergrunddienst (z. B. Sprachaufnahme), zeigt Android eine dauerhafte Benachrichtigung mit Stopp-Aktion. Die App darf diese Benachrichtigung nicht ausblenden.",
  ],
  [
    "Externer Dateiauswähler",
    "Datei- oder Bildauswahl übergibt an den System-Picker (Storage Access Framework), die App erhält nur die freigegebene Datei, keinen vollen Speicherzugriff.",
  ],
];

/**
 * Documented UI behaviour only. No claim about a working Android build,
 * this is the specification the shell components above must honour.
 */
function AndroidSystemInteractionSection() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="label-system pb-2">System-Zurück-Zuordnung</h3>
        <div className="overflow-x-auto border border-border-soft">
          <table className="w-full min-w-[560px] border-collapse text-[12px]">
            <tbody className="divide-y divide-border-soft">
              {backMappingRows.map(([k, v]) => (
                <tr key={k}>
                  <th scope="row" className="w-1/3 px-3 py-2 text-left align-top font-normal text-foreground">
                    {k}
                  </th>
                  <td className="px-3 py-2 align-top text-muted-foreground">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="label-system pb-2">Systemübergaben</h3>
        <div className="overflow-x-auto border border-border-soft">
          <table className="w-full min-w-[560px] border-collapse text-[12px]">
            <tbody className="divide-y divide-border-soft">
              {systemInteractionRows.map(([k, v]) => (
                <tr key={k}>
                  <th scope="row" className="w-1/3 px-3 py-2 text-left align-top font-normal text-foreground">
                    {k}
                  </th>
                  <td className="px-3 py-2 align-top text-muted-foreground">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
