import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { Button, BottomSheet, Dialog, InlineNotice } from "@/components/jarvis/controls";
import {
  ActionResult,
  DESIGN_STATE_ACTION,
  PrototypeBanner,
  useActionResult,
} from "@/components/jarvis/prototype-state";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import type { PrivacyMode } from "@/lib/jarvis/ia";

/**
 * Privacy: hard architecture boundary, explained plus a local mode selector.
 *
 * The real PrivacyGate is not wired in this phase. The selector below only
 * ever changes local, in-memory prototype state so the mode change flow can
 * be reviewed; it never touches the global comparison baseline and never
 * claims to change runtime policy. Browser incognito is not privacy.
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

const modeRank: Record<PrivacyMode, number> = {
  NORMAL: 0,
  PRIVACY: 1,
  PRIVACY_LOCK: 2,
};

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

/** Affected capability groups shown per target mode in the explanation sheet. */
const affectedGroupsByMode: Record<PrivacyMode, string[]> = {
  NORMAL: [],
  PRIVACY: ["Aufnahme", "Beobachtung"],
  PRIVACY_LOCK: ["Aufnahme", "Beobachtung", "Externe Ausführung"],
};

/** Compact "Was sich ändert" summary per target mode. */
const changeSummaryByMode: Record<PrivacyMode, string> = {
  NORMAL:
    "Alle geschützten Pfade werden wieder freigegeben. Aufnahme, Beobachtung, externe Ausführung und Protokollierung laufen wieder wie im normalen Betrieb.",
  PRIVACY:
    "Aufnahme- und Beobachtungspfade (Mikrofon, STT, Bildschirm, Kamera, Zwischenablage, Dateisystem-Beobachtung) werden gesperrt. JARVIS bleibt sonst nutzbar.",
  PRIVACY_LOCK:
    "Zusätzlich zu Aufnahme und Beobachtung werden externe Ausführungspfade (Cloud-Modelle, entfernte Werkzeuge) hart gesperrt.",
};

type Overlay =
  | { kind: "none" }
  | { kind: "explain"; target: PrivacyMode }
  | { kind: "confirm_lock"; target: PrivacyMode }
  | { kind: "confirm_relax"; target: PrivacyMode };

export function PrivacyScreen({ onBack }: SystemDetailProps) {
  const baseline = comparisonBaseline.privacyMode;
  const [selectedMode, setSelectedMode] = useState<PrivacyMode>(baseline);
  const [overlay, setOverlay] = useState<Overlay>({ kind: "none" });
  const { message, report } = useActionResult();

  function closeOverlay() {
    setOverlay({ kind: "none" });
  }

  function requestMode(target: PrivacyMode) {
    if (target === selectedMode) return;
    if (modeRank[target] > modeRank[selectedMode]) {
      setOverlay({ kind: "explain", target });
    } else {
      setOverlay({ kind: "confirm_relax", target });
    }
  }

  function applyMode(target: PrivacyMode) {
    setSelectedMode(target);
    closeOverlay();
    report(`Modus auf ${target} gesetzt (nur lokale Auswahl). ${DESIGN_STATE_ACTION}`);
  }

  function continueFromExplanation(target: PrivacyMode) {
    if (target === "PRIVACY_LOCK") {
      setOverlay({ kind: "confirm_lock", target });
    } else {
      applyMode(target);
    }
  }

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Privacy" subtitle="Schutzgrenzen" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <PrototypeBanner>
          Das echte PrivacyGate ist hier nicht gebunden. Diese Auswahl ist eine lokale
          Vorschau der Moduswechsel-Abfolge und ändert keine Laufzeit-Policy.
        </PrototypeBanner>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Modus auswählen</SectionHeader>
        <ListGroup>
          {modes.map((mode) => (
            <ListRow
              key={mode}
              title={<PrivacyTag mode={mode} />}
              subtitle={modeCopy[mode]}
              selected={mode === selectedMode}
              onClick={() => requestMode(mode)}
              trailing={
                mode === selectedMode ? (
                  <StatusTag state="design_state" label="Ausgewählt (Entwurf)" dot={false} />
                ) : undefined
              }
            />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Ein Wechsel in einen strengeren Modus zeigt zuerst eine Erklärung der
          betroffenen Fähigkeiten. PRIVACY_LOCK und die Rückkehr zu NORMAL verlangen
          zusätzlich eine ausdrückliche Bestätigung.
        </p>
        <ActionResult message={message} />
        <p className="px-4 pt-1 text-[11px] leading-4 text-muted-foreground">
          Referenzwert der Projektbasis: <span className="value-mono">{baseline}</span>{" "}
          (unverändert, unabhängig von dieser Auswahl).
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Geschützte Fähigkeiten</SectionHeader>
        <ListGroup>
          {protectedGroups.map((group) => (
            <ListRow key={group.title} title={group.title} subtitle={group.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Garantien</SectionHeader>
        <ListGroup>
          {guarantees.map((line) => (
            <ListRow key={line} title={line} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Status</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Das zentrale Privacy-Gate ist noch nicht implementiert. Beschrieben ist die
            Zielarchitektur: eine einzige Prüfstelle, die geschützte Fähigkeiten vor der
            Ausführung sperrt, statt sie nachträglich zu filtern.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>

      <BottomSheet
        open={overlay.kind === "explain"}
        onClose={closeOverlay}
        title="Was sich ändert"
      >
        {overlay.kind === "explain" ? (
          <>
            <p className="px-4 pb-2 text-[12px] leading-5 text-subtle-foreground">
              Wechsel zu <PrivacyTag mode={overlay.target} className="align-middle" />:{" "}
              {changeSummaryByMode[overlay.target]}
            </p>
            <SectionHeader>Betroffene Fähigkeitsgruppen</SectionHeader>
            <ListGroup>
              {affectedGroupsByMode[overlay.target].map((title) => {
                const group = protectedGroups.find((g) => g.title === title);
                return <ListRow key={title} title={title} subtitle={group?.detail} />;
              })}
            </ListGroup>
            <div className="flex gap-2 px-4 pt-4">
              <Button onClick={closeOverlay}>Abbrechen</Button>
              <Button variant="primary" onClick={() => continueFromExplanation(overlay.target)}>
                Fortfahren
              </Button>
            </div>
          </>
        ) : null}
      </BottomSheet>

      <Dialog
        open={overlay.kind === "confirm_lock"}
        onClose={closeOverlay}
        title="PRIVACY_LOCK aktivieren"
        description="Diese Stufe sperrt zusätzlich externe Ausführungspfade. Das ist eine lokale Entwurfsauswahl, keine Runtime-Aktion. Wirklich fortfahren?"
      >
        <Button onClick={closeOverlay}>Abbrechen</Button>
        <Button
          variant="destructive"
          onClick={() => overlay.kind === "confirm_lock" && applyMode(overlay.target)}
        >
          PRIVACY_LOCK bestätigen
        </Button>
      </Dialog>

      <Dialog
        open={overlay.kind === "confirm_relax"}
        onClose={closeOverlay}
        title="Weniger strengen Modus wählen"
        description={
          overlay.kind === "confirm_relax"
            ? `Wechsel zu ${overlay.target}. Zuvor gesperrte Fähigkeiten würden wieder freigegeben. Das ist eine lokale Entwurfsauswahl, keine Runtime-Aktion. Wirklich fortfahren?`
            : undefined
        }
      >
        <Button onClick={closeOverlay}>Abbrechen</Button>
        <Button
          variant="primary"
          onClick={() => overlay.kind === "confirm_relax" && applyMode(overlay.target)}
        >
          Bestätigen
        </Button>
      </Dialog>
    </ScrollBody>
  );
}
