import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, Pencil, Plus, Trash2 } from "lucide-react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  Divider,
  ExecutionTag,
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
} from "@/components/jarvis/primitives";
import {
  BottomSheet,
  Button,
  Dialog,
  InlineNotice,
  TextInput,
  Toggle,
} from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import { DetailHeader } from "@/components/jarvis/screens/detail-header";
import { ActionResult, DESIGN_STATE_ACTION, useActionResult } from "@/components/jarvis/prototype-state";
import type { ExecutionLocation, PrivacyMode } from "@/lib/jarvis/ia";
import { automationTypeLabel, type AutomationType } from "@/components/jarvis/screens/automations-screen";

/**
 * Automation editor: local, in-memory prototype editor for Makro, Zeitplan
 * and Routine entries. Nothing here reaches an Android scheduler or runtime.
 * Saving only changes React state held by the parent Automationen screen.
 *
 * Compose mapping: AutomationEditorScreen(draft, onSave, onDelete, onClose).
 */

export interface AutomationStep {
  id: string;
  label: string;
}

export interface AutomationCondition {
  id: string;
  text: string;
}

export type AutomationRuntime = Extract<ExecutionLocation, "LOKAL" | "SLEEPY" | "CLOUD">;

export interface AutomationDraft {
  id: string;
  type: AutomationType;
  name: string;
  purpose: string;
  enabled: boolean;
  runtime: AutomationRuntime;
  privacy: PrivacyMode;
  permissions: string[];
  steps: AutomationStep[];
  scheduleMode: "datetime" | "interval";
  scheduleDateTime: string;
  scheduleInterval: string;
  conditionLogic: "UND" | "ODER";
  conditions: AutomationCondition[];
}

let localIdSeq = 0;
export function nextLocalId(prefix: string): string {
  localIdSeq += 1;
  return `${prefix}-${localIdSeq}`;
}

export function createEmptyDraft(type: AutomationType): AutomationDraft {
  return {
    id: nextLocalId("automation"),
    type,
    name: "",
    purpose: "",
    enabled: false,
    runtime: "LOKAL",
    privacy: "NORMAL",
    permissions: [],
    steps: [],
    scheduleMode: "datetime",
    scheduleDateTime: "",
    scheduleInterval: "",
    conditionLogic: "UND",
    conditions: [],
  };
}

const RUNTIME_OPTIONS: { value: AutomationRuntime; label: string; detail: string }[] = [
  { value: "LOKAL", label: "LOKAL", detail: "Läuft auf dem Gerät, ohne Netzwerkschritt." },
  { value: "SLEEPY", label: "SLEEPY", detail: "Optionale Übergabe an die vertraute Runtime Sleepy, nur wenn verbunden und ausdrücklich freigegeben." },
  { value: "CLOUD", label: "CLOUD", detail: "Braucht einen Cloud-Weg mit vorheriger Freigabe." },
];

const PRIVACY_OPTIONS: { value: PrivacyMode; label: string; detail: string }[] = [
  { value: "NORMAL", label: "NORMAL", detail: "Normaler Betrieb." },
  { value: "PRIVACY", label: "PRIVACY", detail: "Geschützte Wahrnehmungs- und Aufnahmepfade sind gesperrt." },
  { value: "PRIVACY_LOCK", label: "PRIVACY_LOCK", detail: "Zusätzlich können Netzwerk-, Cloud- und externe Werkzeugpfade hart gesperrt sein." },
];

const PERMISSION_OPTIONS = [
  "Standort",
  "Kalender",
  "Kontakte",
  "Benachrichtigungen",
  "Mikrofon",
  "Kamera",
  "Bedienungshilfen (Accessibility)",
];

function stepListLabel(type: AutomationType): { heading: string; addLabel: string; empty: string } {
  if (type === "macro") {
    return {
      heading: "Aktionsreihenfolge",
      addLabel: "Aktion hinzufügen",
      empty: "Noch keine Aktion angelegt. Ein Makro braucht mindestens eine Aktion.",
    };
  }
  return {
    heading: "Schritte",
    addLabel: "Schritt hinzufügen",
    empty: "Noch kein Schritt angelegt. Mindestens ein Schritt ist nötig.",
  };
}

function validateDraft(draft: AutomationDraft): string[] {
  const errors: string[] = [];
  if (draft.name.trim().length === 0) {
    errors.push("Ein Name ist erforderlich.");
  }
  if (draft.steps.length === 0) {
    errors.push(
      draft.type === "macro"
        ? "Mindestens eine Aktion ist erforderlich."
        : "Mindestens ein Schritt ist erforderlich.",
    );
  }
  if (draft.type === "schedule") {
    if (draft.scheduleMode === "datetime" && draft.scheduleDateTime.trim().length === 0) {
      errors.push("Ein Zeitpunkt ist erforderlich, wenn kein Intervall gewählt ist.");
    }
    if (draft.scheduleMode === "interval" && draft.scheduleInterval.trim().length === 0) {
      errors.push("Ein Intervall ist erforderlich, wenn kein Zeitpunkt gewählt ist.");
    }
  }
  if (draft.type === "routine" && draft.conditions.length === 0) {
    errors.push("Mindestens eine Bedingung ist erforderlich.");
  }
  return errors;
}

function derivedNextRun(draft: AutomationDraft): string | null {
  if (draft.type !== "schedule") return null;
  if (draft.scheduleMode === "datetime" && draft.scheduleDateTime.trim().length > 0) {
    return `${draft.scheduleDateTime} (aus der Eingabe berechnet, keine geplante Ausführung)`;
  }
  if (draft.scheduleMode === "interval" && draft.scheduleInterval.trim().length > 0) {
    return `Alle ${draft.scheduleInterval} (aus der Eingabe berechnet, keine geplante Ausführung)`;
  }
  return null;
}

export function AutomationEditor({
  mode,
  initial,
  onSave,
  onDelete,
  onClose,
}: {
  mode: "create" | "edit";
  initial: AutomationDraft;
  onSave: (draft: AutomationDraft) => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<AutomationDraft>(initial);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [stepSheet, setStepSheet] = useState<{ id: string | null; label: string } | null>(null);
  const [conditionSheet, setConditionSheet] = useState<{ id: string | null; text: string } | null>(null);
  const { message, report } = useActionResult();

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(initial), [draft, initial]);
  const errors = useMemo(() => validateDraft(draft), [draft]);
  const nextRun = useMemo(() => derivedNextRun(draft), [draft]);
  const stepLabels = stepListLabel(draft.type);

  const requestClose = () => {
    if (dirty) {
      setDiscardOpen(true);
    } else {
      onClose();
    }
  };

  const handleSave = () => {
    if (errors.length > 0) {
      report(`Speichern nicht möglich: ${errors[0]}`);
      return;
    }
    onSave(draft);
    report(`Änderungen lokal übernommen. ${DESIGN_STATE_ACTION}`);
  };

  const togglePermission = (permission: string) => {
    setDraft((d) => ({
      ...d,
      permissions: d.permissions.includes(permission)
        ? d.permissions.filter((p) => p !== permission)
        : [...d.permissions, permission],
    }));
  };

  const moveStep = (id: string, dir: -1 | 1) => {
    setDraft((d) => {
      const index = d.steps.findIndex((s) => s.id === id);
      const target = index + dir;
      if (index < 0 || target < 0 || target >= d.steps.length) return d;
      const steps = [...d.steps];
      const [item] = steps.splice(index, 1);
      steps.splice(target, 0, item!);
      return { ...d, steps };
    });
  };

  const removeStep = (id: string) => {
    setDraft((d) => ({ ...d, steps: d.steps.filter((s) => s.id !== id) }));
  };

  const saveStep = () => {
    if (!stepSheet || stepSheet.label.trim().length === 0) return;
    setDraft((d) => {
      if (stepSheet.id) {
        return {
          ...d,
          steps: d.steps.map((s) => (s.id === stepSheet.id ? { ...s, label: stepSheet.label } : s)),
        };
      }
      return { ...d, steps: [...d.steps, { id: nextLocalId("step"), label: stepSheet.label }] };
    });
    setStepSheet(null);
  };

  const removeCondition = (id: string) => {
    setDraft((d) => ({ ...d, conditions: d.conditions.filter((c) => c.id !== id) }));
  };

  const saveCondition = () => {
    if (!conditionSheet || conditionSheet.text.trim().length === 0) return;
    setDraft((d) => {
      if (conditionSheet.id) {
        return {
          ...d,
          conditions: d.conditions.map((c) =>
            c.id === conditionSheet.id ? { ...c, text: conditionSheet.text } : c,
          ),
        };
      }
      return {
        ...d,
        conditions: [...d.conditions, { id: nextLocalId("condition"), text: conditionSheet.text }],
      };
    });
    setConditionSheet(null);
  };

  return (
    <>
      <ScrollBody>
        <SectionEnter index={0}>
          <DetailHeader
            title={mode === "create" ? `Neue Automation: ${automationTypeLabel[draft.type]}` : draft.name || "Automation bearbeiten"}
            subtitle={`${automationTypeLabel[draft.type]}, lokaler Editor-Entwurf`}
            onBack={requestClose}
            backLabel="Zurück zu Automationen"
          />
        </SectionEnter>

        <SectionEnter index={1}>
          <SectionHeader>Grunddaten</SectionHeader>
          <div className="flex flex-col gap-3 pb-1">
            <TextInput
              id="automation-name"
              label="Name"
              value={draft.name}
              onChange={(v) => setDraft((d) => ({ ...d, name: v }))}
              placeholder="Name der Automation"
            />
            <div className="px-4">
              <label htmlFor="automation-purpose" className="label-system block pb-1.5">
                Beschreibung / Zweck
              </label>
              <textarea
                id="automation-purpose"
                value={draft.purpose}
                onChange={(e) => setDraft((d) => ({ ...d, purpose: e.target.value }))}
                placeholder="Wofür ist diese Automation gedacht"
                rows={2}
                className="min-h-12 w-full rounded-sm border border-border bg-surface px-3 py-2 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/70"
              />
            </div>
          </div>
          <ListGroup className="mt-2">
            <ListRow
              title="Aktiviert"
              subtitle="Nur lokaler Schalter im Editor, keine Runtime-Wirkung."
              trailing={
                <Toggle
                  checked={draft.enabled}
                  onChange={(v) => setDraft((d) => ({ ...d, enabled: v }))}
                  label="Automation aktiviert"
                />
              }
            />
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={2}>
          <SectionHeader>Ausführungsruntime</SectionHeader>
          <InlineNotice tone="info">
            CLOUD und SLEEPY sind hier nur auswählbare Entwurfsoptionen. Die Auswahl macht diese
            Runtimes nicht verfügbar oder autorisiert.
          </InlineNotice>
          <ListGroup>
            {RUNTIME_OPTIONS.map((opt) => (
              <ListRow
                key={opt.value}
                title={opt.label}
                subtitle={opt.detail}
                selected={draft.runtime === opt.value}
                onClick={() => setDraft((d) => ({ ...d, runtime: opt.value }))}
                trailing={<ExecutionTag where={opt.value} />}
              />
            ))}
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={3}>
          <SectionHeader>Privacy-Kontext</SectionHeader>
          <ListGroup>
            {PRIVACY_OPTIONS.map((opt) => (
              <ListRow
                key={opt.value}
                title={opt.label}
                subtitle={opt.detail}
                selected={draft.privacy === opt.value}
                onClick={() => setDraft((d) => ({ ...d, privacy: opt.value }))}
                trailing={<PrivacyTag mode={opt.value} />}
              />
            ))}
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={4}>
          <SectionHeader>Benötigte Berechtigungen</SectionHeader>
          <InlineNotice tone="info">
            Auswahl beschreibt nur den Bedarf. Keine Berechtigung wird hier erteilt, das bleibt
            Sache des Android-Systemdialogs.
          </InlineNotice>
          <ListGroup className="mt-2">
            {PERMISSION_OPTIONS.map((permission) => (
              <ListRow
                key={permission}
                title={permission}
                trailing={
                  <Toggle
                    checked={draft.permissions.includes(permission)}
                    onChange={() => togglePermission(permission)}
                    label={`Berechtigung ${permission} als benötigt markieren`}
                  />
                }
              />
            ))}
          </ListGroup>
        </SectionEnter>

        {draft.type === "schedule" ? (
          <SectionEnter index={5}>
            <SectionHeader>Zeitplan</SectionHeader>
            <div className="flex gap-2 px-4 pb-2">
              <Button
                variant={draft.scheduleMode === "datetime" ? "primary" : "secondary"}
                onClick={() => setDraft((d) => ({ ...d, scheduleMode: "datetime" }))}
              >
                Datum/Uhrzeit
              </Button>
              <Button
                variant={draft.scheduleMode === "interval" ? "primary" : "secondary"}
                onClick={() => setDraft((d) => ({ ...d, scheduleMode: "interval" }))}
              >
                Intervall
              </Button>
            </div>
            {draft.scheduleMode === "datetime" ? (
              <div className="px-4">
                <label htmlFor="schedule-datetime" className="label-system block pb-1.5">
                  Datum und Uhrzeit
                </label>
                <input
                  id="schedule-datetime"
                  type="datetime-local"
                  value={draft.scheduleDateTime}
                  onChange={(e) => setDraft((d) => ({ ...d, scheduleDateTime: e.target.value }))}
                  className="min-h-12 w-full rounded-sm border border-border bg-surface px-3 text-[13px] text-foreground outline-none focus:border-primary/70"
                />
              </div>
            ) : (
              <TextInput
                id="schedule-interval"
                label="Intervall (z. B. 2 Stunden)"
                value={draft.scheduleInterval}
                onChange={(v) => setDraft((d) => ({ ...d, scheduleInterval: v }))}
                placeholder="Intervall eingeben"
              />
            )}
            <div className="px-4 pt-3">
              <InlineNotice tone="info">
                Nächste Ausführung: {nextRun ?? "noch keine gültige Eingabe vorhanden"}
              </InlineNotice>
            </div>
          </SectionEnter>
        ) : null}

        {draft.type === "routine" ? (
          <SectionEnter index={5}>
            <SectionHeader
              action={
                <Button onClick={() => setConditionSheet({ id: null, text: "" })}>
                  <Plus className="mr-1.5 size-4" aria-hidden />
                  Bedingung
                </Button>
              }
            >
              Bedingungen
            </SectionHeader>
            <div className="flex gap-2 px-4 pb-2">
              <Button
                variant={draft.conditionLogic === "UND" ? "primary" : "secondary"}
                onClick={() => setDraft((d) => ({ ...d, conditionLogic: "UND" }))}
              >
                UND
              </Button>
              <Button
                variant={draft.conditionLogic === "ODER" ? "primary" : "secondary"}
                onClick={() => setDraft((d) => ({ ...d, conditionLogic: "ODER" }))}
              >
                ODER
              </Button>
            </div>
            {draft.conditions.length === 0 ? (
              <InlineNotice tone="warning">Noch keine Bedingung angelegt.</InlineNotice>
            ) : (
              <ListGroup>
                {draft.conditions.map((c, i) => (
                  <ListRow
                    key={c.id}
                    title={`${i > 0 ? `${draft.conditionLogic} ` : ""}${c.text}`}
                    trailing={
                      <span className="flex items-center gap-1">
                        <IconButton
                          label={`Bedingung ${c.text} bearbeiten`}
                          onClick={() => setConditionSheet({ id: c.id, text: c.text })}
                        >
                          <Pencil className="size-4" aria-hidden />
                        </IconButton>
                        <IconButton
                          label={`Bedingung ${c.text} entfernen`}
                          onClick={() => removeCondition(c.id)}
                        >
                          <Trash2 className="size-4" aria-hidden />
                        </IconButton>
                      </span>
                    }
                  />
                ))}
              </ListGroup>
            )}
          </SectionEnter>
        ) : null}

        <SectionEnter index={6}>
          <SectionHeader
            action={
              <Button onClick={() => setStepSheet({ id: null, label: "" })}>
                <Plus className="mr-1.5 size-4" aria-hidden />
                {stepLabels.addLabel}
              </Button>
            }
          >
            {stepLabels.heading}
          </SectionHeader>
          {draft.steps.length === 0 ? (
            <InlineNotice tone="warning">{stepLabels.empty}</InlineNotice>
          ) : (
            <ListGroup>
              {draft.steps.map((step, i) => (
                <ListRow
                  key={step.id}
                  leading={
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[11px]">
                      {i + 1}
                    </span>
                  }
                  title={step.label}
                  trailing={
                    <span className="flex items-center gap-1">
                      <IconButton
                        label={`Schritt ${step.label} nach oben verschieben`}
                        onClick={() => moveStep(step.id, -1)}
                        disabled={i === 0}
                      >
                        <ArrowUp className="size-4" aria-hidden />
                      </IconButton>
                      <IconButton
                        label={`Schritt ${step.label} nach unten verschieben`}
                        onClick={() => moveStep(step.id, 1)}
                        disabled={i === draft.steps.length - 1}
                      >
                        <ArrowDown className="size-4" aria-hidden />
                      </IconButton>
                      <IconButton
                        label={`Schritt ${step.label} bearbeiten`}
                        onClick={() => setStepSheet({ id: step.id, label: step.label })}
                      >
                        <Pencil className="size-4" aria-hidden />
                      </IconButton>
                      <IconButton
                        label={`Schritt ${step.label} entfernen`}
                        onClick={() => removeStep(step.id)}
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </IconButton>
                    </span>
                  }
                />
              ))}
            </ListGroup>
          )}
        </SectionEnter>

        <SectionEnter index={7}>
          <SectionHeader>Validierung</SectionHeader>
          <div className="px-4">
            {errors.length === 0 ? (
              <InlineNotice tone="info">Alle Pflichtangaben sind vollständig.</InlineNotice>
            ) : (
              <InlineNotice tone="error">
                Speichern noch nicht möglich: {errors.join(" ")}
              </InlineNotice>
            )}
          </div>
        </SectionEnter>

        <SectionEnter index={8}>
          <Divider className="my-4" />
          <div className="flex flex-col gap-2 px-4 pb-2">
            <Button variant="primary" full disabled={errors.length > 0} onClick={handleSave}>
              Speichern
            </Button>
            <Button full onClick={requestClose}>
              Verwerfen
            </Button>
            {mode === "edit" && onDelete ? (
              <Button variant="destructive" full onClick={() => setDeleteOpen(true)}>
                Automation löschen
              </Button>
            ) : null}
          </div>
          <ActionResult message={message} />
          <p className="px-4 pt-3 text-[11px] leading-4 text-muted-foreground">
            {DESIGN_STATE_ACTION} Änderungen bleiben lokaler Editor-Zustand dieses Prototyps, es
            wird kein Android-Scheduler und keine Runtime angesprochen.
          </p>
        </SectionEnter>
      </ScrollBody>

      <BottomSheet
        open={stepSheet !== null}
        onClose={() => setStepSheet(null)}
        title={stepSheet?.id ? "Schritt bearbeiten" : "Schritt hinzufügen"}
      >
        <div className="flex flex-col gap-3 pt-2">
          <TextInput
            id="step-label"
            label={draft.type === "macro" ? "Aktion" : "Schritt"}
            value={stepSheet?.label ?? ""}
            onChange={(v) => setStepSheet((s) => (s ? { ...s, label: v } : s))}
            placeholder="Kurze, eindeutige Bezeichnung"
          />
          <div className="flex gap-2 px-4">
            <Button variant="primary" full onClick={saveStep}>
              Übernehmen
            </Button>
            <Button full onClick={() => setStepSheet(null)}>
              Abbrechen
            </Button>
          </div>
        </div>
      </BottomSheet>

      <BottomSheet
        open={conditionSheet !== null}
        onClose={() => setConditionSheet(null)}
        title={conditionSheet?.id ? "Bedingung bearbeiten" : "Bedingung hinzufügen"}
      >
        <div className="flex flex-col gap-3 pt-2">
          <TextInput
            id="condition-text"
            label="Bedingung"
            value={conditionSheet?.text ?? ""}
            onChange={(v) => setConditionSheet((s) => (s ? { ...s, text: v } : s))}
            placeholder="z. B. WLAN verbunden"
          />
          <div className="flex gap-2 px-4">
            <Button variant="primary" full onClick={saveCondition}>
              Übernehmen
            </Button>
            <Button full onClick={() => setConditionSheet(null)}>
              Abbrechen
            </Button>
          </div>
        </div>
      </BottomSheet>

      <Dialog
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        title="Änderungen verwerfen?"
        description="Es gibt ungespeicherte Änderungen in diesem Editor. Sie gehen beim Verlassen verloren."
      >
        <Button onClick={() => setDiscardOpen(false)}>Zurück zum Editor</Button>
        <Button
          variant="destructive"
          onClick={() => {
            setDiscardOpen(false);
            onClose();
          }}
        >
          Verwerfen
        </Button>
      </Dialog>

      <Dialog
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Automation löschen?"
        description="Der Eintrag wird nur aus dem lokalen Editor-Zustand dieses Prototyps entfernt, keine Android-Automation wird gelöscht."
      >
        <Button onClick={() => setDeleteOpen(false)}>Abbrechen</Button>
        <Button
          variant="destructive"
          onClick={() => {
            setDeleteOpen(false);
            onDelete?.();
          }}
        >
          Löschen
        </Button>
      </Dialog>
    </>
  );
}

function IconButton({
  label,
  onClick,
  disabled = false,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="j-pressable flex size-12 items-center justify-center rounded-sm text-muted-foreground disabled:opacity-30"
    >
      {children}
    </button>
  );
}
