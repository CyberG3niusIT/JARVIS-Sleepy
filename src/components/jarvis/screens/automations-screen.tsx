import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ExecutionTag, ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { BottomSheet, Button, EmptyState, InlineNotice } from "@/components/jarvis/controls";
import { ScreenTransition, SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import { DEMO_AREA_NOTE, DESIGN_STATE_ACTION, useActionResult, ActionResult } from "@/components/jarvis/prototype-state";
import {
  AutomationEditor,
  createEmptyDraft,
  type AutomationDraft,
} from "@/components/jarvis/screens/automation-editor";
import type { ExecutionLocation, PrivacyMode, SystemState } from "@/lib/jarvis/ia";

/**
 * Automationen: explicit, bounded local routines.
 *
 * The Android foundation carries background scheduling, but no automation
 * inventory is bound here. The editor below only edits a local, in-memory
 * prototype list held by this screen; nothing is created, scheduled or
 * stored on a device by this screen.
 *
 * Compose mapping: AutomationsScreen(state, onBack), AutomationListItem,
 * NewAutomationSheet, AutomationEditorScreen.
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

function draftSummary(draft: AutomationDraft): string {
  if (draft.type === "schedule") {
    return draft.scheduleMode === "datetime"
      ? draft.scheduleDateTime || "Kein Zeitpunkt festgelegt"
      : draft.scheduleInterval
        ? `Alle ${draft.scheduleInterval}`
        : "Kein Intervall festgelegt";
  }
  if (draft.type === "routine") {
    return draft.conditions.length > 0
      ? `${draft.conditions.length} Bedingung(en), ${draft.conditionLogic}`
      : "Keine Bedingung festgelegt";
  }
  return draft.steps.length > 0 ? `${draft.steps.length} Aktion(en)` : "Keine Aktion festgelegt";
}

export function AutomationsScreen({ onBack }: DetailScreenProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [choice, setChoice] = useState<AutomationType | null>(null);
  /**
   * Local prototype list, held only in this component's React state. It is
   * editor state produced inside this UI, not device data or a bound
   * automation inventory.
   */
  const [automations, setAutomations] = useState<AutomationDraft[]>([]);
  const [editor, setEditor] = useState<
    { mode: "create" | "edit"; draft: AutomationDraft } | null
  >(null);
  const { message, report } = useActionResult();

  const closeSheet = () => {
    setSheetOpen(false);
    setChoice(null);
  };

  const openCreateEditor = (type: AutomationType) => {
    setSheetOpen(false);
    setChoice(null);
    setEditor({ mode: "create", draft: createEmptyDraft(type) });
  };

  const openEditEditor = (draft: AutomationDraft) => {
    setEditor({ mode: "edit", draft });
  };

  const handleSave = (draft: AutomationDraft) => {
    setAutomations((list) => {
      const exists = list.some((a) => a.id === draft.id);
      return exists ? list.map((a) => (a.id === draft.id ? draft : a)) : [...list, draft];
    });
    setEditor((current) => (current ? { ...current, mode: "edit", draft } : current));
  };

  const handleDelete = () => {
    if (!editor) return;
    setAutomations((list) => list.filter((a) => a.id !== editor.draft.id));
    setEditor(null);
    report(`Automation lokal entfernt. ${DESIGN_STATE_ACTION}`);
  };

  return (
    <ScreenTransition
      transitionKey={editor ? "editor" : "overview"}
      direction={editor ? "forward" : "back"}
      className="min-h-full"
    >
      {editor ? (
        <AutomationEditor
          mode={editor.mode}
          initial={editor.draft}
          onSave={handleSave}
          {...(editor.mode === "edit" ? { onDelete: handleDelete } : {})}
          onClose={() => setEditor(null)}
        />
      ) : (
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
                    body="Die Automationsverwaltung ist im Entwurfszustand noch nicht an eine Runtime gebunden. Der Editor unten legt Einträge nur lokal in dieser Sitzung an."
                  />
                </div>
              ) : (
                <>
                  <div className="px-4 pb-2">
                    <InlineNotice tone="info">{DEMO_AREA_NOTE} Liste unten ist lokaler Editor-Zustand.</InlineNotice>
                  </div>
                  <ListGroup>
                    {automations.map((a) => (
                      <ListRow
                        key={a.id}
                        title={a.name || "Ohne Namen"}
                        subtitle={`${automationTypeLabel[a.type]}, ${draftSummary(a)}`}
                        leading={<StatusTag state={a.enabled ? "ready" : "offline"} label={a.enabled ? "Aktiviert" : "Deaktiviert"} />}
                        trailing={<ExecutionTag where={a.runtime} />}
                        chevron
                        onClick={() => openEditEditor(a)}
                      />
                    ))}
                  </ListGroup>
                </>
              )}
              <div className="px-4 pt-3">
                <Button variant="primary" full onClick={() => setSheetOpen(true)}>
                  Neue Automation
                </Button>
              </div>
              <ActionResult message={message} />
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
            onOpenEditor={openCreateEditor}
          />
        </>
      )}
    </ScreenTransition>
  );
}

/* ---------------------------- New automation ----------------------------- */

function NewAutomationSheet({
  open,
  choice,
  onSelect,
  onBackToChoice,
  onClose,
  onOpenEditor,
}: {
  open: boolean;
  choice: AutomationType | null;
  onSelect: (next: AutomationType) => void;
  onBackToChoice: () => void;
  onClose: () => void;
  onOpenEditor: (type: AutomationType) => void;
}) {
  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={choice ? automationTypeLabel[choice] : "Neue Automation"}
    >
      {choice ? (
        <div className="flex flex-col gap-3 px-4 pt-3">
          <InlineNotice tone="info">
            Der Editor legt diese Automation nur lokal in dieser Sitzung an, ohne Android-Scheduler
            und ohne Runtime-Bindung.
          </InlineNotice>
          <div className="flex gap-2">
            <Button onClick={onBackToChoice}>Zurück</Button>
            <Button variant="primary" full onClick={() => onOpenEditor(choice)}>
              Editor öffnen
            </Button>
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
