import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { InlineNotice } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import type { PrivacyMode } from "@/lib/jarvis/ia";

/**
 * Privacy: hard architecture boundary, explained read only.
 *
 * The mode list is presentation, not control: the privacy gate is not wired in
 * this phase, so no control here may claim to change runtime policy and the
 * global baseline stays untouched. Browser incognito is not privacy.
 *
 * Compose mapping: PrivacyScreen(mode, onBack), PrivacyModeRow.
 */

const modeCopy: Record<PrivacyMode, string> = {
  NORMAL: "Normaler Betrieb.",
  PRIVACY:
    "JARVIS-Vorgänge laufen weiter, geschützte Wahrnehmungs- und Aufnahmepfade sind jedoch gesperrt.",
  PRIVACY_LOCK:
    "Strengere Stufe. Zusätzlich können Netzwerk, Cloud und externe Werkzeugpfade hart gesperrt werden.",
};

const modes: PrivacyMode[] = ["NORMAL", "PRIVACY", "PRIVACY_LOCK"];

const protectedGroups = [
  {
    title: "Aufnahme",
    detail: "MIC_INGEST, STT, SCREEN_CAPTURE, CAMERA_CAPTURE, CLIPBOARD_READ",
  },
  {
    title: "Beobachtung",
    detail: "FILESYSTEM_OBSERVATION, PROACTIVE_OBSERVATION",
  },
  {
    title: "Verarbeitung und Gedächtnis",
    detail: "MEMORY_EXTRACT, MEMORY_WRITE, EMBEDDING_GENERATE, SESSION_SUMMARY, AGENT_CONTEXT_INGEST",
  },
  {
    title: "Externe Ausführung",
    detail: "CLOUD_LLM, REMOTE_TOOL",
  },
  {
    title: "Protokollierung",
    detail: "CONTENT_LOGGING",
  },
];

const guarantees = [
  "Kein stiller Cloud-Fallback.",
  "Keine nachträgliche Aufnahme geschützter Inhalte.",
  "Blockierte Daten gelangen nicht in Memory, Logs, Agenten oder eine entfernte Runtime.",
];

export function PrivacyScreen({ onBack }: SystemDetailProps) {
  const current = comparisonBaseline.privacyMode;

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Privacy" subtitle="Schutzgrenzen" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Aktueller Modus</SectionHeader>
        <ListGroup>
          {modes.map((mode) => (
            <ListRow
              key={mode}
              title={<PrivacyTag mode={mode} />}
              subtitle={modeCopy[mode]}
              selected={mode === current}
              trailing={
                mode === current ? (
                  <StatusTag state="design_state" label="Aktiv" dot={false} />
                ) : undefined
              }
            />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Die Auswahl ist im Entwurfszustand schreibgeschützt. Ein Moduswechsel wird erst
          möglich, wenn die Privacy-Prüfung an die Runtime gebunden ist.
        </p>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Geschützte Fähigkeiten</SectionHeader>
        <ListGroup>
          {protectedGroups.map((group) => (
            <ListRow key={group.title} title={group.title} subtitle={group.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Garantien</SectionHeader>
        <ListGroup>
          {guarantees.map((line) => (
            <ListRow key={line} title={line} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Status</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Das zentrale Privacy-Gate ist noch nicht implementiert. Beschrieben ist die
            Zielarchitektur: eine einzige Prüfstelle, die geschützte Fähigkeiten vor der
            Ausführung sperrt, statt sie nachträglich zu filtern.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={5}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
