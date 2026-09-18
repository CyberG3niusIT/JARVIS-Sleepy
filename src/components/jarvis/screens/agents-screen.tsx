import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { EmptyState } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import type { ExecutionLocation, PrivacyMode, SystemState } from "@/lib/jarvis/ia";

/**
 * Agenten: management and observability surface for bounded task agents.
 *
 * Capability audit: AgentLoop, PlanManager, ReEvaluationEngine and
 * IntentClassifier exist and are modified; ActionSequenceExecutor is kept.
 * An agent never gains more authority than its calling context. Nothing here
 * is a live inventory: there is no verified agent list and no counter.
 *
 * Compose mapping: AgentsScreen(state, onBack), AgentListItem.
 */

/* ------------------------------ Agent model ------------------------------ */

/** Reusable entry for future real agents. Deliberately unpopulated. */
export interface AgentEntry {
  id: string;
  name: string;
  purpose: string;
  state: SystemState;
  /** Tools the agent may call, never wider than the calling context. */
  allowedTools: string[];
  runtime: ExecutionLocation;
  privacyContext: PrivacyMode;
  currentTask?: string;
  /** Step budget and time budget, both enforced, both reported when known. */
  maxSteps?: number;
  timeoutSeconds?: number;
}

export function AgentListItem({ agent }: { agent: AgentEntry }) {
  const subtitle = [agent.purpose, agent.currentTask].filter(Boolean).join(", ");
  return (
    <ListRow
      title={agent.name}
      subtitle={subtitle}
      trailing={<StatusTag state={agent.state} dot={false} />}
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

export function AgentsScreen({ onBack }: SystemDetailProps) {
  /** No verified agent inventory exists in this phase. */
  const agents: AgentEntry[] = [];

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
        <SectionHeader>Sicherheitsgrenzen</SectionHeader>
        <ListGroup>
          {safetyBounds.map((rule) => (
            <ListRow key={rule} title={rule} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
