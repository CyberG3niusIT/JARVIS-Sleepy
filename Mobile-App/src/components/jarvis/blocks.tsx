import { cn } from "@/lib/utils";
import {
  capabilityRows,
  routingLadder,
  stateLabel,
  type PrivacyMode,
} from "@/lib/jarvis/ia";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import {
  DesignStateBlock,
  ExecutionTag,
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "./primitives";

/**
 * Content blocks shared by all shell prototypes (A, B, C, D), so the variants differ
 * in navigation and density rather than in fabricated content.
 * No value below is runtime data.
 */

export function RuntimeSummary({ compact = false }: { compact?: boolean }) {
  return (
    <ListGroup>
      <ListRow
        title="Lokale Runtime"
        subtitle={compact ? undefined : "LiteRT-LM, kein Modell gebunden"}
        trailing={
          <StatusTag
            state="design_state"
            label={comparisonBaseline.labels.localModel}
          />
        }
      />
      <ListRow
        title="Ausführungsort"
        subtitle={compact ? undefined : "Standard: lokal, kein stiller Fallback"}
        trailing={<ExecutionTag where={comparisonBaseline.execution} />}
      />
      <ListRow
        title="Vertraute Runtime (Sleepy)"
        subtitle={compact ? undefined : "Optionaler begrenzter Handoff"}
        trailing={
          <StatusTag state="unavailable" label={comparisonBaseline.labels.sleepy} />
        }
      />
      <ListRow
        title="Berechtigungen"
        subtitle={
          compact ? undefined : "Android-Zugriffe, Status noch nicht vollständig gebunden"
        }
        trailing={
          <StatusTag
            state="permission_required"
            label={comparisonBaseline.labels.permissions}
          />
        }
      />
    </ListGroup>
  );
}

export function PrivacyBlock({
  mode = comparisonBaseline.privacyMode,
}: {
  mode?: PrivacyMode;
}) {
  const modes: PrivacyMode[] = ["NORMAL", "PRIVACY", "PRIVACY_LOCK"];
  return (
    <div className="px-4">
      <div
        className="flex overflow-hidden rounded-sm border border-border"
        role="group"
        aria-label="Privacy Mode"
      >
        {modes.map((m) => (
          <span
            key={m}
            className={cn(
              "flex-1 py-2 text-center font-mono text-[10px] tracking-wider",
              m === mode
                ? "bg-surface-selected text-primary"
                : "text-muted-foreground",
            )}
          >
            {m}
          </span>
        ))}
      </div>
      <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
        Privacy Mode ist eine harte Grenze, keine Voreinstellung. PRIVACY blockiert
        geschützte Wahrnehmungs- und Datenpfade. PRIVACY_LOCK kann zusätzlich
        Netzwerk-, Cloud- und externe Tool-Pfade hart sperren.
      </p>
    </div>
  );
}

export function RoutingLadderBlock({
  limit,
  steps,
  localSteps = 6,
}: {
  limit?: number;
  steps?: string[];
  /** How many leading steps run locally, so the tag stays truthful per list. */
  localSteps?: number;
}) {
  const source = steps ?? routingLadder;
  const items = limit ? source.slice(0, limit) : source;
  return (
    <ol className="divide-y divide-border-soft border-y border-border-soft bg-surface">
      {items.map((step, i) => (
        <li key={step} className="flex items-center gap-3 px-4 py-2">
          <span className="value-mono w-4 shrink-0 text-right">{i + 1}</span>
          <span className="flex-1 text-[12px] leading-4 text-subtle-foreground">{step}</span>
          {i < localSteps ? <ExecutionTag where="LOKAL" /> : null}
        </li>
      ))}
    </ol>
  );
}

export function CapabilityList({ dense = false }: { dense?: boolean }) {
  return (
    <ListGroup>
      {capabilityRows.map((c) => (
        <ListRow
          key={c.name}
          title={c.name}
          subtitle={dense ? undefined : c.detail}
          trailing={
            <span className="flex items-center gap-2">
              <StatusTag
                state={c.state}
                {...(c.statusLabel ? { label: c.statusLabel } : {})}
                dot={false}
              />
              <ExecutionTag where={c.execution} />
            </span>
          }
        />
      ))}
    </ListGroup>
  );
}

/** Chat entry point. Answers carry their execution location. */
export function ChatThread({ full = false }: { full?: boolean }) {
  return (
    <div className={cn("flex flex-col gap-3 px-4 py-3", full && "min-h-full")}>
      <Turn who="user" text="Stell das Handy auf lautlos und wecke mich um 6:30." />
      <Turn
        who="jarvis"
        text="Zwei Android-Aktionen vorbereitet. Ausführung deterministisch, ohne Modell."
        where="LOKAL"
        actions={["Lautlos aktivieren", "Wecker 06:30"]}
      />
      <Turn
        who="user"
        text="Fasse die PDF auf dem Bildschirm zusammen."
      />
      <Turn
        who="jarvis"
        text="Bildschirmanalyse benötigt die Android-Berechtigung für Bildschirmzugriff. Ohne Freigabe passiert nichts, kein stiller Fallback und keine automatische Übergabe."
        state="permission_required"
      />
    </div>
  );
}

function Turn({
  who,
  text,
  where,
  state,
  actions,
}: {
  who: "user" | "jarvis";
  text: string;
  where?: "LOKAL" | "SLEEPY" | "CLOUD" | "EXTERN";
  state?: "permission_required";
  actions?: string[];
}) {
  if (who === "user") {
    return (
      <div className="self-end max-w-[78%] rounded-sm rounded-br-xs bg-surface-selected px-3 py-2">
        <p className="text-[13px] leading-5 text-foreground">{text}</p>
      </div>
    );
  }
  return (
    <div className="max-w-[88%] border-l-2 border-border pl-3">
      <div className="mb-1 flex items-center gap-2">
        {where ? <ExecutionTag where={where} /> : null}
        {state ? <StatusTag state={state} /> : null}
      </div>
      <p className="text-[13px] leading-5 text-subtle-foreground">{text}</p>
      {actions ? (
        <ul className="mt-2 divide-y divide-border-soft rounded-sm border border-border-soft">
          {actions.map((a) => (
            <li key={a} className="flex items-center justify-between px-2.5 py-2">
              <span className="text-[12px] text-foreground">{a}</span>
              <span className="value-mono">bestätigen</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Composer of the historical variants and of the design system reference.
 * The field is only a button when it has a real target, and Senden stays
 * disabled without a send callback, so no control pretends to work.
 */
export function Composer({
  hint = "Lokal fragen oder Aktion nennen",
  onFocusField,
  onSend,
  fieldLabel,
}: {
  hint?: string;
  onFocusField?: () => void;
  onSend?: () => void;
  fieldLabel?: string;
}) {
  const fieldClass =
    "touch-row flex flex-1 items-center rounded-sm border border-border px-3 text-left text-[13px] text-muted-foreground";
  return (
    <div className="flex items-center gap-2 border-t border-border-soft bg-surface px-3 py-2">
      {onFocusField ? (
        <button
          type="button"
          onClick={onFocusField}
          aria-label={fieldLabel}
          className={cn("j-pressable focus:border-primary/70", fieldClass)}
        >
          {hint}
        </button>
      ) : (
        <div className={fieldClass} aria-hidden>
          {hint}
        </div>
      )}
      <button
        type="button"
        onClick={onSend}
        disabled={!onSend}
        className={cn(
          "touch-row flex min-w-12 items-center justify-center rounded-sm border px-3 text-[12px]",
          onSend
            ? "j-pressable border-primary/50 text-primary"
            : "border-border-soft text-disabled",
        )}
      >
        Senden
      </button>
    </div>
  );
}

/**
 * Content of the Einstellungen destination in the historical variants A, B and C.
 * Informational rows only: these reference shells have no settings detail screen,
 * so no chevron and no empty handler pretends navigation exists.
 */
export function SettingsList() {
  return (
    <ListGroup>
      <ListRow title="Sprache & Ausgabe" subtitle="Deutsch" />
      <ListRow title="Darstellung" subtitle="Dunkel, Systemdichte" />
      <ListRow title="Speicher & Modelle" trailing={<StatusTag state="design_state" />} />
      <ListRow title="Hintergrunddienst" trailing={<StatusTag state="design_state" />} />
    </ListGroup>
  );
}

export function NotBoundNotice() {
  return (
    <div className="px-4 pt-3">
      <DesignStateBlock
        state="design_state"
        note={`Prototyp ohne Runtime-Anbindung. Alle Zustände sind Entwurfszustände (${stateLabel.design_state}) und keine gemessenen Werte.`}
      />
    </div>
  );
}

export { SectionHeader };
