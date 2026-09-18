import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ModelsScreen } from "@/components/jarvis/screens/models-screen";
import { PrivacyBlock, RoutingLadderBlock } from "@/components/jarvis/blocks";
import {
  ExecutionTag,
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { ScreenTransition, SectionEnter, ValueTransition } from "@/components/jarvis/motion";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import {
  stateLabel,
  systemDestinations,
  type AreaId,
  type SystemState,
} from "@/lib/jarvis/ia";

/**
 * System: technical control center of JARVIS Mobile (Phase 5, page 3).
 *
 * Answers at a glance: current local system state, which technical areas
 * exist, which of them need attention, privacy mode, default execution
 * location and the full local-first decision order.
 *
 * Titles, descriptions and order come from the locked Phase 4 information
 * architecture, states come from comparisonBaseline and the capability audit.
 * Nothing is measured: no telemetry, no counters, no health score. Detail
 * pages do not exist yet, so the destination rows stay informational and
 * deliberately carry no chevron and no dead tap target.
 *
 * Compose mapping: SystemScreen(state: SystemUiState), SystemAreaRow.
 */

/**
 * Truthful status label per destination, only where the current baseline
 * actually knows one. The tone still comes from the audited area state.
 */
const areaStatusLabel: Partial<Record<AreaId, string>> = {
  models: comparisonBaseline.labels.localModel,
  permissions: comparisonBaseline.labels.permissions,
  privacy: comparisonBaseline.privacyMode,
  runtimes: comparisonBaseline.labels.runtime,
  diagnostics: "Keine Runtime-Daten",
};

/**
 * Display state for this overview only. Runtimes reports the unbound local
 * runtime here, so tone and label match. The locked IA state and the fact that
 * the Sleepy handoff is not implemented stay untouched.
 */
const areaDisplayState: Partial<Record<AreaId, SystemState>> = {
  runtimes: "design_state",
};

/**
 * Destinations with a real detail screen. Every other row stays informational,
 * so no row pretends to navigate. Extending this list is the only step needed
 * once Agenten, Tools, Berechtigungen, Privacy, Runtimes, Gerät or Logs follow.
 */
const navigableAreas: AreaId[] = ["models"];

/**
 * System tab container: control-center overview plus its detail screens.
 * The bottom navigation keeps System selected while a detail is open, and back
 * returns to the overview with the opposite direction.
 */
export function SystemScreen() {
  const [detail, setDetail] = useState<AreaId | null>(null);

  return (
    <ScreenTransition
      transitionKey={detail ?? "overview"}
      direction={detail ? "forward" : "back"}
      className="min-h-full"
    >
      {detail === "models" ? (
        <ModelsScreen onBack={() => setDetail(null)} />
      ) : (
        <SystemOverview onOpenArea={setDetail} />
      )}
    </ScreenTransition>
  );
}

function SystemOverview({ onOpenArea }: { onOpenArea: (area: AreaId) => void }) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <SystemHeader />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Systemzustand</SectionHeader>
        <ListGroup>
          <ListRow
            title="Lokale Runtime"
            trailing={
              <StatusTag state="design_state" label={comparisonBaseline.labels.runtime} />
            }
          />
          <ListRow
            title="Standardausführung"
            trailing={<ExecutionTag where={comparisonBaseline.execution} />}
          />
          <ListRow
            title="Privacy"
            trailing={
              <ValueTransition value={comparisonBaseline.privacyMode}>
                <PrivacyTag mode={comparisonBaseline.privacyMode} />
              </ValueTransition>
            }
          />
          <ListRow
            title="Berechtigungen"
            trailing={
              <StatusTag
                state="permission_required"
                label={comparisonBaseline.labels.permissions}
              />
            }
          />
          <ListRow
            title="Lokales Modell"
            trailing={
              <StatusTag
                state="design_state"
                label={comparisonBaseline.labels.localModel}
              />
            }
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Kontrollbereiche</SectionHeader>
        <ListGroup>
          {systemDestinations.map((area) => {
            const display = areaDisplayState[area.id] ?? area.state;
            const navigable = navigableAreas.includes(area.id);
            return (
              <ListRow
                key={area.id}
                title={area.label}
                subtitle={area.purpose}
                trailing={
                  <StatusTag
                    state={display}
                    label={areaStatusLabel[area.id] ?? stateLabel[display]}
                    dot={false}
                  />
                }
                chevron={navigable}
                {...(navigable ? { onClick: () => onOpenArea(area.id) } : {})}
              />
            );
          })}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Teile der Tools und Android-Aktionen hängen von freigegebenen Berechtigungen
          ab. Detailansichten sind in dieser Phase noch nicht geöffnet.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Benötigt Aufmerksamkeit</SectionHeader>
        <ListGroup>
          <ListRow
            title="Lokales Modell"
            subtitle="Modellgestützte lokale Antworten sind erst nach dem Laden eines Modells verfügbar."
            trailing={
              <StatusTag
                state="design_state"
                label={comparisonBaseline.labels.localModel}
              />
            }
          />
          <ListRow
            title="Berechtigungen"
            subtitle="Benötigte Android-Berechtigungen sind noch nicht vollständig freigegeben."
            trailing={
              <StatusTag
                state="permission_required"
                label={comparisonBaseline.labels.permissions}
              />
            }
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Sleepy und Cloud sind optional und zählen deshalb nicht als Blocker.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Privacy</SectionHeader>
        <PrivacyBlock mode={comparisonBaseline.privacyMode} />
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Vollständige Entscheidungsreihenfolge</SectionHeader>
        <RoutingLadderBlock />
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Deterministische Android-Aktionen zuerst, lokale Skills und Tools vor
          generativer Antwort, lokales Modell vor vertrauenswürdiger Runtime. Sleepy
          bleibt optional, ein Cloud-Fallback nur nach Freigabe. Kein stiller Fallback.
        </p>
      </SectionEnter>

      <SectionEnter index={6}>
        <p className="px-4 pt-5 pb-1 text-[11px] leading-4 text-muted-foreground">
          {stateLabel.design_state}. Angezeigte Zustände stammen aus der aktuellen
          Projektbasis, nicht aus gemessener Laufzeittelemetrie.
        </p>
      </SectionEnter>
    </ScrollBody>
  );
}

/** Compact functional page header. No hero, no marketing copy. */
function SystemHeader() {
  return (
    <div className="border-b border-border-soft bg-surface px-4 py-4">
      <h1 className="text-[15px] leading-5 text-foreground">System</h1>
      <p className="mt-1 text-[13px] leading-5 text-subtle-foreground">Kontrollzentrum</p>
    </div>
  );
}
