import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ExecutionTag,
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import {
  HandoffReviewSection,
  SleepyPairingSection,
  TrustInspectionSection,
} from "@/components/jarvis/screens/runtimes-demo";

/**
 * Runtimes: trusted execution locations, not remote monitoring.
 *
 * J.A.R.V.I.S Mobile is independently useful. Sleepy is an optional trusted
 * runtime; pairing, identity, transport and handoff are future work and stay
 * reported as not implemented. No pairing code, no latency, no connectivity
 * claim beyond the documented baseline.
 *
 * Compose mapping: RuntimesScreen(state, onBack), RuntimeListItem.
 */

const handoffStructure = [
  { title: "Aufgabe", detail: "Klar begrenztes Ziel der Übergabe." },
  { title: "Freigegebener Kontext", detail: "Nur ausdrücklich freigegebene Inhalte." },
  { title: "Privacy-Zustand", detail: "Der Modus des Aufrufkontexts wird mitgeführt." },
  { title: "Limits", detail: "Schritt-, Zeit- und Werkzeuggrenzen." },
  { title: "Erwartetes Ergebnis", detail: "Vereinbarte Form der Antwort." },
  { title: "Rückkanal", detail: "Definierter Weg für Ergebnis, Abbruch und Fehler." },
];

export function RuntimesScreen({ onBack }: SystemDetailProps) {
  const { labels } = comparisonBaseline;

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Runtimes" subtitle="Ausführungsorte" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Dieses Gerät</SectionHeader>
        <ListGroup>
          <ListRow
            title="J.A.R.V.I.S Mobile"
            subtitle="Vorgesehene lokale Runtime auf diesem Android-Gerät."
            trailing={<StatusTag state="design_state" label={labels.runtime} dot={false} />}
          />
          <ListRow
            title="Standardausführung"
            trailing={<ExecutionTag where={comparisonBaseline.execution} />}
          />
          <ListRow
            title="Vorgesehene Inferenz"
            trailing={<span className="value-mono">{labels.modelRuntime}</span>}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Vertraute Runtime</SectionHeader>
        <ListGroup>
          <ListRow
            title="Sleepy"
            subtitle="Optionale vertraute Ausführungsumgebung, nicht erforderlich für den lokalen Betrieb."
            trailing={<StatusTag state="unavailable" label={labels.sleepy} dot={false} />}
          />
          <ListRow
            title="Übergabe"
            trailing={
              <StatusTag state="not_implemented" label={labels.sleepyHandoff} dot={false} />
            }
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Cloud</SectionHeader>
        <ListGroup>
          <ListRow
            title="Cloud-Ausführung"
            subtitle="Nur nach ausdrücklicher Freigabe, niemals als Standardweg."
            trailing={<StatusTag state="design_state" label={labels.cloud} dot={false} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Handoff-Prinzip</SectionHeader>
        <ListGroup>
          {handoffStructure.map((row) => (
            <ListRow key={row.title} title={row.title} subtitle={row.detail} />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Beschreibt die Zielstruktur einer Übergabe. Es findet keine Kopplung und keine
          Übergabe statt.
        </p>
      </SectionEnter>

      <SleepyPairingSection />
      <TrustInspectionSection />
      <HandoffReviewSection />

      <SectionEnter index={9}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
