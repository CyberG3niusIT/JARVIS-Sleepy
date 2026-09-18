import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  stateLabel,
  type ExecutionLocation,
  type PrivacyMode,
  type SystemState,
} from "@/lib/jarvis/ia";

/**
 * Shared JARVIS UI primitives.
 * Each maps to a Compose composable named in Brand Spec §32:
 *   StatusTag, ExecutionTag, JarvisListRow, SettingsGroup, SectionHeader.
 */

const stateTone: Record<SystemState, string> = {
  ready: "text-success",
  local: "text-primary",
  sleepy: "text-primary",
  waiting_remote: "text-warning",
  offline: "text-muted-foreground",
  unavailable: "text-muted-foreground",
  permission_required: "text-warning",
  privacy_blocked: "text-warning",
  error: "text-destructive",
  not_implemented: "text-muted-foreground",
  degraded: "text-warning",
  design_state: "text-muted-foreground",
};

const stateDot: Record<SystemState, string> = {
  ready: "bg-success",
  local: "bg-primary",
  sleepy: "bg-primary",
  waiting_remote: "bg-warning",
  offline: "bg-disabled",
  unavailable: "bg-disabled",
  permission_required: "bg-warning",
  privacy_blocked: "bg-warning",
  error: "bg-destructive",
  not_implemented: "bg-disabled",
  degraded: "bg-warning",
  design_state: "bg-disabled",
};

export function StatusTag({
  state,
  label,
  dot = true,
  className,
}: {
  state: SystemState;
  label?: string;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 text-[11px] leading-4",
        stateTone[state],
        className,
      )}
    >
      {dot ? (
        <span className={cn("size-1.5 rounded-full", stateDot[state])} aria-hidden />
      ) : null}
      {label ?? stateLabel[state]}
    </span>
  );
}

const execTone: Record<ExecutionLocation, string> = {
  LOKAL: "border-primary/50 text-primary",
  SLEEPY: "border-border text-subtle-foreground",
  CLOUD: "border-warning/50 text-warning",
  EXTERN: "border-border text-muted-foreground",
};

export function ExecutionTag({
  where,
  className,
}: {
  where: ExecutionLocation;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-xs border px-1.5 py-px font-mono text-[10px] leading-4 tracking-wider",
        execTone[where],
        className,
      )}
    >
      {where}
    </span>
  );
}

export function PrivacyTag({
  mode,
  className,
}: {
  mode: PrivacyMode;
  className?: string;
}) {
  const tone =
    mode === "NORMAL"
      ? "text-subtle-foreground"
      : mode === "PRIVACY"
        ? "text-primary"
        : "text-warning";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] tracking-wider",
        tone,
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {mode}
    </span>
  );
}

export function SectionHeader({
  children,
  action,
  className,
}: {
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-end justify-between px-4 pt-5 pb-2", className)}>
      <h2 className="label-system">{children}</h2>
      {action}
    </div>
  );
}

/** Dense functional row — the core list unit. 48 dp minimum touch target. */
export function ListRow({
  title,
  subtitle,
  leading,
  trailing,
  chevron = false,
  selected = false,
  onClick,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  leading?: ReactNode;
  trailing?: ReactNode;
  chevron?: boolean;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "touch-row flex w-full items-center gap-3 px-4 py-2.5 text-left",
        onClick && "j-pressable",
        selected && "bg-surface-selected",
        className,
      )}
    >
      {leading ? <span className="shrink-0 text-muted-foreground">{leading}</span> : null}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] leading-5 text-foreground">{title}</span>
        {subtitle ? (
          <span className="mt-0.5 block truncate text-[11px] leading-4 text-muted-foreground">
            {subtitle}
          </span>
        ) : null}
      </span>
      {trailing}
      {chevron ? (
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      ) : null}
    </Comp>
  );
}

/** Grouped list container with hairline dividers, Android settings style. */
export function ListGroup({
  children,
  className,
  flush = false,
}: {
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <div
      className={cn(
        "divide-y divide-border-soft border-y border-border-soft bg-surface",
        !flush && "mx-0",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Explicit design-state placeholder. Used wherever a runtime value would be —
 * never a fabricated number.
 */
export function DesignStateBlock({
  state,
  note,
  className,
}: {
  state: SystemState;
  note?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1 rounded-sm border border-dashed border-border px-3 py-3",
        className,
      )}
    >
      <StatusTag state={state} />
      {note ? (
        <p className="text-[11px] leading-4 text-muted-foreground">{note}</p>
      ) : null}
    </div>
  );
}

export function Divider({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-border-soft", className)} aria-hidden />;
}
