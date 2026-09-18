import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ExecutionTag,
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { BottomSheet } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import { DetailField } from "@/components/jarvis/prototype-state";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { capabilityRows, stateLabel, type CapabilityRow } from "@/lib/jarvis/ia";

/**
 * Tools: capability inventory and execution policy.
 *
 * Rows come from the audited capabilityRows, so nothing is invented here and
 * the audit stays the single source. Rows are informational, not toggles: tool
 * access is policy controlled, not a per-row switch in the prototype. Tapping
 * a row opens a read-only detail sheet built only from audited fields already
 * present on the capability; anything not tracked there reads "Nicht
 * festgelegt" instead of a guessed value.
 *
 * Compose mapping: ToolsScreen(capabilities, onBack), CapabilityListItem,
 * CapabilityDetailSheet.
 */

const NOT_SET = "Nicht festgelegt";

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
  const [selected, setSelected] = useState<CapabilityRow | null>(null);

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
              onClick={() => setSelected(row)}
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
          Runtime. Eine Fähigkeit antippen zeigt die geprüften Details.
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

      <BottomSheet
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected ? selected.name : "Fähigkeit"}
      >
        {selected ? (
          <>
            <DetailField label="Beschreibung">{selected.detail}</DetailField>
            <DetailField label="Ausführungsort">
              <ExecutionTag where={selected.execution} />
            </DetailField>
            <DetailField label="Prüfzustand">
              <StatusTag
                state={selected.state}
                {...(selected.statusLabel ? { label: selected.statusLabel } : {})}
                dot={false}
              />
            </DetailField>
            <DetailField label="Statusbezeichnung">
              {selected.statusLabel ?? stateLabel[selected.state]}
            </DetailField>
            <DetailField label="Berechtigungsabhängigkeit">{NOT_SET}</DetailField>
            <DetailField label="Privacy-Sensibilität">{NOT_SET}</DetailField>
            <DetailField label="Audit-Entscheidung">{selected.decision}</DetailField>
            <p className="px-4 pt-2 pb-1 text-[11px] leading-4 text-muted-foreground">
              Diese Ansicht zeigt ausschließlich geprüfte Angaben aus der Fähigkeitsprüfung.
              Es gibt hier keinen Schalter und keine Ausführungsfunktion.
            </p>
          </>
        ) : null}
      </BottomSheet>
    </ScrollBody>
  );
}
