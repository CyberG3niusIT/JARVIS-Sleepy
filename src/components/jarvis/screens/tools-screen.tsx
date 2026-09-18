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
import { capabilityRows } from "@/lib/jarvis/ia";

/**
 * Tools: capability inventory and execution policy.
 *
 * Rows come from the audited capabilityRows, so nothing is invented here and
 * the audit stays the single source. Rows are informational, not toggles: tool
 * access is policy controlled, not a per-row switch in the prototype.
 *
 * Compose mapping: ToolsScreen(capabilities, onBack), CapabilityListItem.
 */

const executionRules = [
  {
    title: "Zugriff über Richtlinie",
    detail: "Tools werden durch die Ausführungsrichtlinie freigegeben, nicht einzeln erraten.",
  },
  {
    title: "Android-Berechtigungen",
    detail: "Ein Teil der Aktionen setzt freigegebene Android-Berechtigungen voraus.",
  },
  {
    title: "Privacy-Grenze",
    detail: "Geschützte Tools werden im Privacy Mode blockiert, ohne stillen Ersatzweg.",
  },
  {
    title: "Keine impliziten Rechte",
    detail: "Eine Modellanfrage erteilt keine Tool-Rechte.",
  },
];

export function ToolsScreen({ onBack }: SystemDetailProps) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Tools" subtitle="Fähigkeiten und Ausführung" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Fähigkeiten</SectionHeader>
        <ListGroup>
          {capabilityRows.map((row) => (
            <ListRow
              key={row.name}
              title={row.name}
              subtitle={row.detail}
              trailing={
                <span className="flex shrink-0 items-center gap-2">
                  <ExecutionTag where={row.execution} />
                  <StatusTag
                    state={row.state}
                    {...(row.statusLabel ? { label: row.statusLabel } : {})}
                    dot={false}
                  />
                </span>
              }
            />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Zustände stammen aus der Fähigkeitsprüfung des Projekts, nicht aus einer laufenden
          Runtime.
        </p>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Ausführungsregeln</SectionHeader>
        <ListGroup>
          {executionRules.map((rule) => (
            <ListRow key={rule.title} title={rule.title} subtitle={rule.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={3}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
