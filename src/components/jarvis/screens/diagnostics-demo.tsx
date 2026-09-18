import { useMemo, useState } from "react";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { BottomSheet, Button, EmptyState, InlineNotice } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import { DEMO_AREA_NOTE, DESIGN_STATE_ACTION, DetailField, useActionResult } from "@/components/jarvis/prototype-state";
import type { LogEntry } from "@/components/jarvis/screens/diagnostics-screen";
import type { ExecutionLocation } from "@/lib/jarvis/ia";

/**
 * Zustandsdemonstration für Logs & Diagnose.
 *
 * Dieser Bereich ist ausdrücklich vom truthful baseline getrennt: die beiden
 * echten Listen (Ausführungshistorie, Crash-Logs) bleiben leer. Hier werden
 * ausschließlich Beispieleinträge mit bereits redigierten Zusammenfassungen
 * gezeigt, es handelt sich um reinen React-Zustand im Speicher, keine
 * Runtime- oder Gerätedaten.
 */

const severityLabel: Record<LogEntry["severity"], string> = {
  info: "Info",
  warn: "Warnung",
  error: "Fehler",
};

const severityTone: Record<LogEntry["severity"], "neutral" | "warning" | "error"> = {
  info: "neutral",
  warn: "warning",
  error: "error",
};

type SeverityFilter = "alle" | LogEntry["severity"];
type RuntimeFilter = "alle" | ExecutionLocation;

const demoEntries: LogEntry[] = [
  {
    id: "demo-hist-1",
    timestamp: "Heute, 09:14",
    category: "Ausführungshistorie",
    severity: "info",
    runtime: "LOKAL",
    redactedSummary: "Kapazität \"Termin anlegen\" lokal ausgeführt, Parameter redigiert",
  },
  {
    id: "demo-hist-2",
    timestamp: "Heute, 09:02",
    category: "Ausführungshistorie",
    severity: "warn",
    runtime: "CLOUD",
    redactedSummary: "Kapazität \"Zusammenfassung erstellen\" an Cloud delegiert, Inhalt minimiert",
  },
  {
    id: "demo-hist-3",
    timestamp: "Gestern, 21:47",
    category: "Ausführungshistorie",
    severity: "error",
    runtime: "SLEEPY",
    redactedSummary: "Kapazität \"Nachricht senden\" fehlgeschlagen, Zugangsdaten redigiert",
  },
  {
    id: "demo-crash-1",
    timestamp: "Gestern, 18:30",
    category: "Absturzprotokoll",
    severity: "error",
    runtime: "LOKAL",
    redactedSummary: "Absturz im Sprachmodul, Stacktrace ohne sensible Parameter",
  },
  {
    id: "demo-crash-2",
    timestamp: "Vorgestern, 07:12",
    category: "Absturzprotokoll",
    severity: "warn",
    runtime: "EXTERN",
    redactedSummary: "Externe Integration antwortete verzögert, Payload redigiert",
  },
];

function DemoLogListItem({ entry, onOpen }: { entry: LogEntry; onOpen: () => void }) {
  return (
    <ListRow
      title={entry.redactedSummary}
      subtitle={`${entry.timestamp}, ${entry.category}`}
      trailing={
        <StatusTag state={severityTone[entry.severity]} label={severityLabel[entry.severity]} dot={false} />
      }
      chevron
      onClick={onOpen}
    />
  );
}

export function DiagnosticsDemoSection() {
  const [severity, setSeverity] = useState<SeverityFilter>("alle");
  const [runtime, setRuntime] = useState<RuntimeFilter>("alle");
  const [openId, setOpenId] = useState<string | null>(null);
  const [exportStep, setExportStep] = useState<"geschlossen" | "pruefen">("geschlossen");
  const { message, report } = useActionResult();

  const runtimes = useMemo<ExecutionLocation[]>(
    () => Array.from(new Set(demoEntries.map((e) => e.runtime))),
    [],
  );

  const filtered = demoEntries.filter((e) => {
    if (severity !== "alle" && e.severity !== severity) return false;
    if (runtime !== "alle" && e.runtime !== runtime) return false;
    return true;
  });

  const open = demoEntries.find((e) => e.id === openId) ?? null;

  const copyRedactedSummary = () => {
    if (!open) return;
    report(`Redigierte Zusammenfassung von "${open.redactedSummary}" wurde im Demozustand als kopiert markiert. ${DESIGN_STATE_ACTION}`);
  };

  const confirmExport = () => {
    setExportStep("geschlossen");
    report(`Diagnoseexport wurde geprüft und bestätigt, es wurde keine Datei erstellt oder heruntergeladen. ${DESIGN_STATE_ACTION}`);
  };

  return (
    <SectionEnter index={6}>
      <SectionHeader>Zustandsdemonstration</SectionHeader>
      <div className="px-4 pb-2">
        <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
      </div>

      <div className="px-4 pb-2">
        <InlineNotice tone="info">
          Redaktion aktiv: sensible Werte wie Zugangsdaten, Nachrichteninhalte und geschützte
          Parameter werden vor der Anzeige entfernt oder gekürzt. Die folgenden Beispieleinträge
          zeigen ausschließlich bereits redigierte Zusammenfassungen.
        </InlineNotice>
      </div>

      <div className="flex flex-col gap-2 px-4 pb-2">
        <span className="label-system">Nach Schweregrad filtern</span>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Nach Schweregrad filtern">
          {(["alle", "info", "warn", "error"] as SeverityFilter[]).map((s) => (
            <Button
              key={s}
              variant={severity === s ? "primary" : "secondary"}
              onClick={() => setSeverity(s)}
              aria-pressed={severity === s}
            >
              {s === "alle" ? "Alle" : severityLabel[s]}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2 px-4 pb-2">
        <span className="label-system">Nach Runtime filtern</span>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Nach Runtime filtern">
          <Button
            variant={runtime === "alle" ? "primary" : "secondary"}
            onClick={() => setRuntime("alle")}
            aria-pressed={runtime === "alle"}
          >
            Alle
          </Button>
          {runtimes.map((r) => (
            <Button
              key={r}
              variant={runtime === r ? "primary" : "secondary"}
              onClick={() => setRuntime(r)}
              aria-pressed={runtime === r}
            >
              {r}
            </Button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="px-4">
          <EmptyState
            title="Keine Einträge für diese Filterkombination"
            body="In dieser Beispielliste passt kein Eintrag zur gewählten Kombination aus Schweregrad und Runtime."
          />
        </div>
      ) : (
        <ListGroup>
          {filtered.map((e) => (
            <DemoLogListItem key={e.id} entry={e} onOpen={() => setOpenId(e.id)} />
          ))}
        </ListGroup>
      )}

      <div className="px-4 pt-2">
        <Button full onClick={() => setExportStep("pruefen")}>
          Diagnose exportieren
        </Button>
      </div>

      <p role="status" aria-live="polite" className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
        {message ?? ""}
      </p>

      <BottomSheet open={!!open} onClose={() => setOpenId(null)} title="Logeintrag (Beispiel)">
        {open ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col">
              <DetailField label="Zeitpunkt">{open.timestamp}</DetailField>
              <DetailField label="Kategorie">{open.category}</DetailField>
              <DetailField label="Schweregrad">
                <StatusTag state={severityTone[open.severity]} label={severityLabel[open.severity]} dot={false} />
              </DetailField>
              <DetailField label="Runtime">{open.runtime}</DetailField>
            </div>
            <div className="px-4">
              <InlineNotice tone="info">
                Redigiert: sensible Werte wurden vor der Anzeige entfernt oder gekürzt.
              </InlineNotice>
            </div>
            <div className="flex flex-col gap-1 px-4">
              <span className="label-system">Redigierte Zusammenfassung</span>
              <p className="rounded-sm border border-border-soft bg-surface-raised px-3 py-2 text-[12px] leading-5 text-subtle-foreground">
                {open.redactedSummary}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 px-4 pb-1">
              <Button onClick={copyRedactedSummary}>Redigierte Zusammenfassung kopieren</Button>
              <Button onClick={() => setOpenId(null)}>Schließen</Button>
            </div>
          </div>
        ) : null}
      </BottomSheet>

      <BottomSheet
        open={exportStep === "pruefen"}
        onClose={() => setExportStep("geschlossen")}
        title="Diagnose exportieren"
      >
        <div className="flex flex-col gap-3">
          <div className="px-4">
            <InlineNotice tone="info">
              Diese Übersicht zeigt, welche Datenkategorien in einem Diagnoseexport enthalten wären.
              Sensible Werte würden vor dem Export redigiert. Im Entwurfszustand wird keine Datei
              erstellt oder heruntergeladen.
            </InlineNotice>
          </div>
          <ListGroup>
            <ListRow title="Ausführungshistorie" subtitle="Zusammenfassungen, redigiert" />
            <ListRow title="Crash-Logs" subtitle="Stacktraces ohne sensible Parameter" />
            <ListRow title="Redaktionsregeln" subtitle="Angewandte Regeln zu diesem Export" />
            <ListRow title="Geräte- und App-Version" subtitle="Ohne persönliche Kennungen" />
          </ListGroup>
          <div className="flex flex-wrap gap-2 px-4 pb-1">
            <Button onClick={() => setExportStep("geschlossen")}>Abbrechen</Button>
            <Button variant="primary" onClick={confirmExport}>
              Export bestätigen
            </Button>
          </div>
        </div>
      </BottomSheet>
    </SectionEnter>
  );
}
