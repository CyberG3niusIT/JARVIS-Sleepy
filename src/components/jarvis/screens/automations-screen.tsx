import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader } from "@/components/jarvis/primitives";
import { BottomSheet, Button, EmptyState, InlineNotice } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import type { ExecutionLocation, PrivacyMode, SystemState } from "@/lib/jarvis/ia";

/**
 * Automationen: explicit, bounded local routines.
 *
 * The Android foundation carries background scheduling, but no automation
 * inventory is bound here. Nothing is created, scheduled or stored by this
 * screen; the type chooser only explains the target flow.
 *
 * Compose mapping: AutomationsScreen(state, onBack), AutomationListItem,
 * NewAutomationSheet.
 */

/* --------------------------- Future data contract ------------------------ */

export type AutomationType = "macro" | "schedule" | "routine";

export const automationTypeLabel: Record<AutomationType, string> = {
  macro: "Makro",
  schedule: "Zeitplan",
  routine: "Routine",
};

/** Reusable entry shape for later real automations. Deliberately unpopulated. */
export interface AutomationEntry {
  id: string;
  name: string;
  type: AutomationType;
  enabled: boolean;
  state: SystemState;
  /** Time, interval or condition, only when it is really defined. */
  trigger?: string;
  /** Where the steps run. */
  runtime: ExecutionLocation;
  /** Android permissions the steps depend on. */
  requiredPermissions?: string[];
  /** Privacy mode the automation was defined for. */
  privacyContext?: PrivacyMode;
}

/* -------------------------------- Content -------------------------------- */

const typeRows: { type: AutomationType; detail: string }[] = [
  { type: "macro", detail: "Mehrere definierte Aktionen in fester Reihenfolge." },
  { type: "schedule", detail: "Ausführung zu einem festgelegten Zeitpunkt oder Intervall." },
  { type: "routine", detail: "Wiederkehrende Abläufe mit klaren Bedingungen und Grenzen." },
];

const executionRules: { title: string; detail: string }[] = [
  {
    title: "Deterministisch vor generativ",
    detail: "Feste Aktionen laufen vor modellgestütztem Verhalten.",
  },
  {
    title: "Berechtigungen bleiben nötig",
    detail: "Eine Automation umgeht keine Android-Berechtigung.",
  },
  {
    title: "Privacy kann blockieren",
    detail: "Geschützte Schritte werden im jeweiligen Modus gesperrt.",
  },
  {
    title: "Keine automatische Cloud-Eskalation",
    detail: "Ein Cloud-Weg entsteht nur nach ausdrücklicher Freigabe.",
  },
  {
    title: "Keine Rechteausweitung",
    detail: "Eine Automation kann ihre eigenen Grenzen nicht erweitern.",
  },
];

export function AutomationsScreen({ onBack }: DetailScreenProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [choice, setChoice] = useState<AutomationType | null>(null);
  /**
   * No automation source is bound in this phase. The empty list describes the
   * missing binding, not a verified absence on a real device.
   */
  const automations: AutomationEntry[] = [];

  const closeSheet = () => {
    setSheetOpen(false);
    setChoice(null);
  };

  return (
    <>
      <ScrollBody>
        <SectionEnter index={0}>
          <DetailHeader
            title="Automationen"
            subtitle="Makros, Zeitpläne und Routinen"
            onBack={onBack}
            backLabel={MORE_BACK_LABEL}
          />
        </SectionEnter>

        <SectionEnter index={1}>
          <SectionHeader>Automationen</SectionHeader>
          {automations.length === 0 ? (
            <div className="px-4">
              <EmptyState
                title="Keine Automationsdaten angebunden"
                body="Die Automationsverwaltung ist im Entwurfszustand noch nicht an eine Runtime gebunden. Makros, Zeitpläne und Routinen werden später hier verwaltet."
              />
            </div>
          ) : (
            <ListGroup>
              {automations.map((a) => (
                <ListRow
                  key={a.id}
                  title={a.name}
                  subtitle={automationTypeLabel[a.type]}
                />
              ))}
            </ListGroup>
          )}
          <div className="px-4 pt-3">
            <Button variant="primary" full onClick={() => setSheetOpen(true)}>
              Neue Automation
            </Button>
          </div>
        </SectionEnter>

        <SectionEnter index={2}>
          <SectionHeader>Typen</SectionHeader>
          <ListGroup>
            {typeRows.map((t) => (
              <ListRow
                key={t.type}
                title={automationTypeLabel[t.type]}
                subtitle={t.detail}
              />
            ))}
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={3}>
          <SectionHeader>Ausführungsregeln</SectionHeader>
          <ListGroup>
            {executionRules.map((r) => (
              <ListRow key={r.title} title={r.title} subtitle={r.detail} />
            ))}
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={4}>
          <DesignStateNote />
        </SectionEnter>
      </ScrollBody>

      <NewAutomationSheet
        open={sheetOpen}
        choice={choice}
        onSelect={setChoice}
        onBackToChoice={() => setChoice(null)}
        onClose={closeSheet}
      />
    </>
  );
}

/* ---------------------------- New automation ----------------------------- */

const choiceCopy: Record<AutomationType, string> = {
  macro: "Editor noch nicht angebunden. Aktionen, Reihenfolge und Grenzen eines Makros werden später hier festgelegt.",
  schedule:
    "Editor noch nicht angebunden. Zeitpunkt, Intervall und Ausführungsbedingungen werden später hier festgelegt.",
  routine:
    "Editor noch nicht angebunden. Bedingungen, Schritte und Grenzen einer Routine werden später hier festgelegt.",
};

function NewAutomationSheet({
  open,
  choice,
  onSelect,
  onBackToChoice,
  onClose,
}: {
  open: boolean;
  choice: AutomationType | null;
  onSelect: (next: AutomationType) => void;
  onBackToChoice: () => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={choice ? automationTypeLabel[choice] : "Neue Automation"}
    >
      {choice ? (
        <div className="flex flex-col gap-3 px-4 pt-3">
          <InlineNotice tone="info">{choiceCopy[choice]}</InlineNotice>
          <div className="flex gap-2">
            <Button onClick={onBackToChoice}>Zurück</Button>
            <Button onClick={onClose}>Schließen</Button>
          </div>
        </div>
      ) : (
        <ListGroup>
          {typeRows.map((t) => (
            <ListRow
              key={t.type}
              title={automationTypeLabel[t.type]}
              subtitle={t.detail}
              chevron
              onClick={() => onSelect(t.type)}
            />
          ))}
        </ListGroup>
      )}
    </BottomSheet>
  );
}
