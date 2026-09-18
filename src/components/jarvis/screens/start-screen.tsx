import { ScrollBody } from "@/components/prototype/phone-frame";
import { PrivacyBlock, RoutingLadderBlock } from "@/components/jarvis/blocks";
import {
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { Button } from "@/components/jarvis/controls";
import { SectionEnter, ValueTransition } from "@/components/jarvis/motion";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import { routingLadderShort, stateLabel } from "@/lib/jarvis/ia";

/**
 * Start: operational overview of JARVIS Mobile (Phase 5, page 1).
 *
 * Answers at a glance: is the local runtime usable, what blocks it, where does
 * work execute, what is the privacy state, is Sleepy available, what is the
 * local-first decision order. No feature management lives here.
 *
 * Every value comes from comparisonBaseline. Nothing is measured, nothing is
 * simulated. Compose mapping: StartScreen(state: StartUiState, onOpenChat, onOpenSystem).
 */

export interface StartScreenProps {
  onOpenChat: () => void;
  onOpenSystem?: () => void;
}

export function StartScreen({ onOpenChat, onOpenSystem }: StartScreenProps) {
  const overall = comparisonBaseline.runtimeBound
    ? "Lokale Runtime bereit"
    : "Lokale Runtime noch nicht vollständig eingerichtet";

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <StatusSummary headline={overall} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Aktuelle Blocker</SectionHeader>
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
          Beides betrifft die volle lokale Fähigkeit. Verwaltet wird es unter System.
        </p>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Optionale Runtimes</SectionHeader>
        <ListGroup>
          <ListRow
            title="Sleepy"
            subtitle="Optionale vertraute Runtime für begrenzte Übergaben."
            trailing={
              <StatusTag state="unavailable" label={comparisonBaseline.labels.sleepy} />
            }
          />
          <ListRow
            title="Cloud"
            subtitle="Optional und nur nach ausdrücklicher Freigabe."
            trailing={
              <StatusTag state="unavailable" label={comparisonBaseline.labels.cloud} />
            }
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Sleepy und Cloud sind für den lokalen Betrieb nicht grundsätzlich erforderlich.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Privacy</SectionHeader>
        <PrivacyBlock mode={comparisonBaseline.privacyMode} />
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Entscheidungsreihenfolge</SectionHeader>
        <RoutingLadderBlock steps={routingLadderShort} localSteps={3} />
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Kurzform. Die vollständige Reihenfolge steht unter System.
        </p>
      </SectionEnter>

      <SectionEnter index={5}>
        <div className="flex flex-col items-stretch gap-2 px-4 pt-5">
          <Button variant="primary" full onClick={onOpenChat}>
            Chat öffnen
          </Button>
          {onOpenSystem ? (
            <button
              type="button"
              onClick={onOpenSystem}
              className="j-pressable min-h-12 rounded-sm text-[12px] text-muted-foreground"
            >
              Zum Kontrollzentrum
            </button>
          ) : null}
        </div>
      </SectionEnter>
    </ScrollBody>
  );
}

/** Compact system-status summary. No hero, no score, no percentage. */
function StatusSummary({ headline }: { headline: string }) {
  return (
    <div className="border-b border-border-soft bg-surface px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[15px] leading-5 text-foreground">J.A.R.V.I.S Mobile</h1>
          <ValueTransition value={headline} className="mt-1">
            <p className="text-[13px] leading-5 text-subtle-foreground">{headline}</p>
          </ValueTransition>
        </div>
        <StatusTag
          state="design_state"
          label={comparisonBaseline.labels.runtime}
          className="mt-0.5"
        />
      </div>
      <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
        {stateLabel.design_state}. Keine gemessenen Laufzeitwerte. Standardausführung:{" "}
        {comparisonBaseline.execution}.
      </p>
    </div>
  );
}
