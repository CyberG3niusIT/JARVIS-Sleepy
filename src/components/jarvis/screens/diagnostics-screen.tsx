import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { EmptyState, InlineNotice } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import type { ExecutionLocation, SystemState } from "@/lib/jarvis/ia";

/**
 * Logs & Diagnose: local diagnosability and audit surface.
 *
 * Crash logging and the redaction of execution history exist in the audit and
 * are kept. There is no prototype log inventory, so both lists stay empty and
 * no entry is fabricated. Export stays informational until a real local file
 * export exists.
 *
 * Compose mapping: DiagnosticsScreen(entries, onBack), LogListItem.
 */

/** Reusable entry for future real log rows. Deliberately unpopulated. */
export interface LogEntry {
  id: string;
  timestamp: string;
  category: string;
  severity: "info" | "warn" | "error";
  runtime: ExecutionLocation;
  /** Summary after redaction, never the raw payload. */
  redactedSummary: string;
  state?: SystemState;
}

export function LogListItem({ entry }: { entry: LogEntry }) {
  return (
    <ListRow
      title={entry.redactedSummary}
      subtitle={`${entry.timestamp}, ${entry.category}`}
      trailing={<span className="value-mono text-muted-foreground">{entry.runtime}</span>}
    />
  );
}

const redactionRules = [
  { title: "Zugangsdaten redigieren", detail: "Schlüssel, Token und Passwörter werden entfernt." },
  { title: "Sensible Parameter redigieren", detail: "Inhaltliche Argumente werden gekürzt." },
  { title: "Kommunikationsinhalte minimieren", detail: "Nachrichtentexte werden nicht abgelegt." },
  { title: "Privacy-Status berücksichtigen", detail: "Geschützte Inhalte werden nicht protokolliert." },
];

export function DiagnosticsScreen({ onBack }: SystemDetailProps) {
  /** No verified log inventory exists in this phase. */
  const executionHistory: LogEntry[] = [];
  const crashLogs: LogEntry[] = [];

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Logs & Diagnose" subtitle="Lokale Diagnose" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Ausführungshistorie</SectionHeader>
        {executionHistory.length === 0 ? (
          <div className="px-4">
            <EmptyState
              title="Keine Runtime-Daten"
              body="Spätere Einträge werden lokal gespeichert und dort redigiert, wo es erforderlich ist. Im Entwurfszustand gibt es keine Historie."
            />
          </div>
        ) : (
          <ListGroup>
            {executionHistory.map((e) => (
              <LogListItem key={e.id} entry={e} />
            ))}
          </ListGroup>
        )}
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Crash-Logs</SectionHeader>
        {crashLogs.length === 0 ? (
          <div className="px-4">
            <EmptyState
              title="Keine Runtime-Daten"
              body="Die Absturzprotokollierung ist Teil der Grundlage, im Entwurfszustand liegen jedoch keine Einträge vor."
            />
          </div>
        ) : (
          <ListGroup>
            {crashLogs.map((e) => (
              <LogListItem key={e.id} entry={e} />
            ))}
          </ListGroup>
        )}
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Redaktion</SectionHeader>
        <ListGroup>
          {redactionRules.map((rule) => (
            <ListRow key={rule.title} title={rule.title} subtitle={rule.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Diagnose</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Ein lokaler Export ist im Entwurfszustand nicht verfügbar. Sobald er umgesetzt ist,
            verlässt eine Diagnosedatei das Gerät nur auf ausdrückliche Freigabe.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={5}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
