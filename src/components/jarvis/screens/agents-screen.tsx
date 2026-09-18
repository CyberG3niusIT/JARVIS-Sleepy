import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag, ExecutionTag, PrivacyTag } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { BottomSheet, Button, EmptyState, InlineNotice } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { ActionResult, DEMO_AREA_NOTE, DESIGN_STATE_ACTION, DetailField, useActionResult } from "@/components/jarvis/prototype-state";
import type { ExecutionLocation, PrivacyMode, SystemState } from "@/lib/jarvis/ia";

/**
 * Agenten: management and observability surface for bounded task agents.
 *
 * Capability audit: AgentLoop, PlanManager, ReEvaluationEngine and
 * IntentClassifier exist and are modified; ActionSequenceExecutor is kept.
 * An agent never gains more authority than its calling context. Nothing here
 * is a live inventory: there is no verified agent list and no counter. The
 * only populated agent lives inside a clearly labelled demonstration section
 * and its detail sheet; cancelling or retrying it only changes that local
 * demo state.
 *
 * Compose mapping: AgentsScreen(state, onBack), AgentListItem,
 * AgentDetailSheet.
 */

/* ------------------------------ Agent model ------------------------------ */

/** Local, demo-only task lifecycle state. Never bound to a real scheduler. */
export type TaskState =
  | "running"
  | "waiting_remote"
  | "completed"
  | "failed"
  | "cancelled";

export const taskStateLabel: Record<TaskState, string> = {
  running: "Läuft",
  waiting_remote: "Wartet auf Sleepy",
  completed: "Abgeschlossen",
  failed: "Fehlgeschlagen",
  cancelled: "Abgebrochen",
};

const taskStateTone: Record<TaskState, SystemState> = {
  running: "local",
  waiting_remote: "waiting_remote",
  completed: "ready",
  failed: "error",
  cancelled: "offline",
};

/** Compact record of a single tool call, for the tool-activity summary only. */
export interface ToolActivityEntry {
  tool: string;
  summary: string;
}

/** Reusable entry for future real agents. Deliberately unpopulated by default. */
export interface AgentEntry {
  id: string;
  name: string;
  purpose: string;
  /** Concrete goal of the current task, distinct from the general purpose. */
  goal: string;
  state: SystemState;
  /** Tools the agent may call, never wider than the calling context. */
  allowedTools: string[];
  runtime: ExecutionLocation;
  privacyContext: PrivacyMode;
  currentTask?: string;
  taskState: TaskState;
  /** Step budget and time budget, both enforced, both reported when known. */
  maxSteps?: number;
  currentStep?: number;
  timeoutSeconds?: number;
  /** Context explicitly approved for the task, never widened by the agent. */
  approvedContext?: string[];
  /** Result the task is expected to deliver, agreed before execution. */
  expectedResult?: string;
  /** Result actually reported back, only once the task produced one. */
  lastResult?: string;
  /** Reason for failure, only present once a task actually failed. */
  errorReason?: string;
  /** Compact, non-fabricated summary of tool calls made during the task. */
  toolActivity: ToolActivityEntry[];
  startedAt?: string;
  updatedAt?: string;
}

export function AgentListItem({
  agent,
  onClick,
}: {
  agent: AgentEntry;
  onClick?: () => void;
}) {
  const subtitle = [agent.purpose, agent.currentTask].filter(Boolean).join(", ");
  return (
    <ListRow
      title={agent.name}
      subtitle={subtitle}
      trailing={<StatusTag state={agent.state} dot={false} />}
      chevron={!!onClick}
      onClick={onClick}
    />
  );
}

const agentModel = [
  { title: "Begrenztes Ziel", detail: "Eine klar umrissene Aufgabe je Agent." },
  { title: "Erlaubte Tools", detail: "Nur ausdrücklich freigegebene Werkzeuge." },
  { title: "Privacy-Kontext", detail: "Der Modus des Aufrufkontexts gilt weiter." },
  { title: "Schrittlimit", detail: "Maximale Anzahl an Planungs- und Ausführungsschritten." },
  { title: "Zeitlimit", detail: "Harte Obergrenze für die Laufzeit einer Aufgabe." },
  { title: "Ausführungsruntime", detail: "Lokal, sofern keine Übergabe freigegeben ist." },
];

const safetyBounds = [
  "Keine Rechteausweitung über den Aufrufkontext hinaus.",
  "Keine automatische Cloud-Freigabe.",
  "Keine Tool-Nutzung außerhalb des erlaubten Kontexts.",
  "Abbruch bei Grenzverletzung oder erreichtem Limit.",
];

/** Example task shown only inside the Zustandsdemonstration section. */
const demoAgent: AgentEntry = {
  id: "demo-agent-1",
  name: "Beispiel-Agent",
  purpose: "Terminvorschlag aus einer Chat-Anfrage ableiten.",
  goal: "Drei passende Terminvorschläge für ein Treffen nächste Woche finden.",
  state: "local",
  allowedTools: ["Kalenderlesezugriff", "Textantwort verfassen"],
  runtime: "LOKAL",
  privacyContext: "NORMAL",
  currentTask: "Terminvorschlag erstellen",
  taskState: "running",
  maxSteps: 6,
  currentStep: 3,
  timeoutSeconds: 90,
  approvedContext: ["Aktueller Chat-Verlauf", "Kalendereinträge der laufenden Woche"],
  expectedResult: "Liste mit drei Terminvorschlägen inklusive Begründung.",
  lastResult: undefined,
  errorReason: undefined,
  toolActivity: [
    { tool: "Kalenderlesezugriff", summary: "Verfügbare Zeitfenster der Woche gelesen." },
    { tool: "Textantwort verfassen", summary: "Entwurf für Terminvorschlag erstellt." },
  ],
  startedAt: "vor 2 Minuten",
  updatedAt: "vor 12 Sekunden",
};

export function AgentsScreen({ onBack }: SystemDetailProps) {
  /** No verified agent inventory exists in this phase. */
  const agents: AgentEntry[] = [];
  const [demo, setDemo] = useState<AgentEntry>(demoAgent);
  const [sheetView, setSheetView] = useState<"closed" | "detail" | "error" | "activity">("closed");
  const { message, report } = useActionResult();

  const cancelTask = () => {
    setDemo((prev) => ({ ...prev, taskState: "cancelled", currentTask: prev.currentTask }));
    report(`Demo-Aufgabe abgebrochen. ${DESIGN_STATE_ACTION}`);
  };

  const retryTask = () => {
    setDemo((prev) => ({
      ...prev,
      taskState: "running",
      currentStep: 1,
      errorReason: undefined,
      lastResult: undefined,
    }));
    report(`Demo-Aufgabe erneut gestartet. ${DESIGN_STATE_ACTION}`);
  };

  const failDemo = () => {
    setDemo((prev) => ({
      ...prev,
      taskState: "failed",
      errorReason: "Zeitlimit vor Abschluss des letzten Schritts erreicht (Demo).",
    }));
    report(`Demo-Aufgabe als fehlgeschlagen markiert. ${DESIGN_STATE_ACTION}`);
  };

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Agenten" subtitle="Begrenzte Ausführung" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Agentenmodell</SectionHeader>
        <ListGroup>
          {agentModel.map((row) => (
            <ListRow key={row.title} title={row.title} subtitle={row.detail} />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Architekturmerkmale des Aufgabenmodells, keine aktuellen Werte.
        </p>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Laufende Aufgaben</SectionHeader>
        {agents.length === 0 ? (
          <div className="px-4">
            <EmptyState
              title="Keine Laufzeitdaten verfügbar"
              body="Die Agentenausführung ist im Entwurfszustand nicht an eine Runtime gebunden. Aufgaben, Schritte und Limits erscheinen hier, sobald sie aus der Runtime gelesen werden."
            />
          </div>
        ) : (
          <ListGroup>
            {agents.map((a) => (
              <AgentListItem key={a.id} agent={a} />
            ))}
          </ListGroup>
        )}
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Zustandsdemonstration</SectionHeader>
        <div className="px-4 pb-2">
          <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
        </div>
        <ListGroup>
          <AgentListItem agent={demo} onClick={() => setSheetView("detail")} />
        </ListGroup>
        <div className="flex gap-2 px-4 pt-3">
          <Button onClick={failDemo}>Demo als fehlgeschlagen markieren</Button>
        </div>
        <ActionResult message={message} />
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Sicherheitsgrenzen</SectionHeader>
        <ListGroup>
          {safetyBounds.map((rule) => (
            <ListRow key={rule} title={rule} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <DesignStateNote />
      </SectionEnter>

      <AgentDetailSheet
        agent={demo}
        view={sheetView}
        onShowDetail={() => setSheetView("detail")}
        onShowError={() => setSheetView("error")}
        onShowActivity={() => setSheetView("activity")}
        onClose={() => setSheetView("closed")}
        onCancel={cancelTask}
        onRetry={retryTask}
      />
    </ScrollBody>
  );
}

/* ------------------------------ Agent detail ------------------------------ */

function AgentDetailSheet({
  agent,
  view,
  onShowDetail,
  onShowError,
  onShowActivity,
  onClose,
  onCancel,
  onRetry,
}: {
  agent: AgentEntry;
  view: "closed" | "detail" | "error" | "activity";
  onShowDetail: () => void;
  onShowError: () => void;
  onShowActivity: () => void;
  onClose: () => void;
  onCancel: () => void;
  onRetry: () => void;
}) {
  const title =
    view === "error"
      ? "Fehlerursache"
      : view === "activity"
        ? "Tool-Aktivität"
        : agent.name;

  return (
    <BottomSheet open={view !== "closed"} onClose={onClose} title={title}>
      {view === "error" ? (
        <div className="flex flex-col gap-3 px-4 pt-3">
          <InlineNotice tone={agent.errorReason ? "error" : "info"}>
            {agent.errorReason ?? "Für diese Demo-Aufgabe liegt aktuell keine Fehlerursache vor."}
          </InlineNotice>
          <Button onClick={onShowDetail}>Zurück zur Aufgabe</Button>
        </div>
      ) : view === "activity" ? (
        <div className="flex flex-col gap-3 px-4 pt-3">
          {agent.toolActivity.length === 0 ? (
            <InlineNotice tone="info">
              Für diese Demo-Aufgabe wurden noch keine Tool-Aufrufe erfasst.
            </InlineNotice>
          ) : (
            <ListGroup>
              {agent.toolActivity.map((entry, i) => (
                <ListRow key={`${entry.tool}-${i}`} title={entry.tool} subtitle={entry.summary} />
              ))}
            </ListGroup>
          )}
          <p className="text-[11px] leading-4 text-muted-foreground">
            {DEMO_AREA_NOTE}
          </p>
          <Button onClick={onShowDetail}>Zurück zur Aufgabe</Button>
        </div>
      ) : (
        <div className="flex flex-col">
          <DetailField label="Ziel">{agent.goal}</DetailField>
          <DetailField label="Zweck">{agent.purpose}</DetailField>
          <DetailField label="Erlaubte Tools">
            <span className="flex flex-col items-end gap-0.5">
              {agent.allowedTools.map((t) => (
                <span key={t}>{t}</span>
              ))}
            </span>
          </DetailField>
          <DetailField label="Freigegebener Kontext">
            {agent.approvedContext && agent.approvedContext.length > 0 ? (
              <span className="flex flex-col items-end gap-0.5">
                {agent.approvedContext.map((c) => (
                  <span key={c}>{c}</span>
                ))}
              </span>
            ) : (
              "Nicht festgelegt"
            )}
          </DetailField>
          <DetailField label="Privacy-Kontext">
            <PrivacyTag mode={agent.privacyContext} />
          </DetailField>
          <DetailField label="Ausführungsruntime">
            <ExecutionTag where={agent.runtime} />
          </DetailField>
          <DetailField label="Maximale Schritte">{agent.maxSteps ?? "Nicht festgelegt"}</DetailField>
          <DetailField label="Aktueller Schritt">
            {agent.currentStep !== undefined ? agent.currentStep : "Nicht bekannt"}
          </DetailField>
          <DetailField label="Schrittzahl">
            {agent.maxSteps !== undefined && agent.currentStep !== undefined
              ? `${agent.currentStep} von ${agent.maxSteps}`
              : "Nicht festgelegt"}
          </DetailField>
          <DetailField label="Zeitlimit">
            {agent.timeoutSeconds !== undefined ? `${agent.timeoutSeconds} s` : "Nicht festgelegt"}
          </DetailField>
          <DetailField label="Erwartetes Ergebnis">
            {agent.expectedResult ?? "Nicht festgelegt"}
          </DetailField>
          <DetailField label="Letztes Ergebnis">
            {agent.lastResult ?? "Noch kein Ergebnis vorhanden"}
          </DetailField>
          <DetailField label="Aufgabenzustand">
            <StatusTag state={taskStateTone[agent.taskState]} label={taskStateLabel[agent.taskState]} dot={false} />
          </DetailField>
          <DetailField label="Startzeit">{agent.startedAt ?? "Nicht bekannt"}</DetailField>
          <DetailField label="Aktualisiert">{agent.updatedAt ?? "Nicht bekannt"}</DetailField>

          <div className="px-4 pt-4">
            <SectionHeader className="px-0 pt-0">Zustandsdemonstration</SectionHeader>
            <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
          </div>

          <div className="flex flex-col gap-2 px-4 pt-3">
            <Button
              variant="destructive"
              full
              disabled={agent.taskState === "cancelled" || agent.taskState === "completed"}
              onClick={onCancel}
            >
              Aufgabe abbrechen (Demo)
            </Button>
            <Button
              full
              disabled={agent.taskState !== "failed"}
              onClick={onRetry}
            >
              Fehlgeschlagene Aufgabe erneut starten (Demo)
            </Button>
            <Button full onClick={onShowError}>
              Fehlerursache ansehen
            </Button>
            <Button full onClick={onShowActivity}>
              Tool-Aktivität ansehen
            </Button>
          </div>
        </div>
      )}
    </BottomSheet>
  );
}
