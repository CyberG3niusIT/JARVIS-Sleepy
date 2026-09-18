import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { InlineNotice } from "@/components/jarvis/controls";

/**
 * Shared prototype truth helpers.
 *
 * Every newly interactive surface in this frontend specification pass may only
 * change local in-memory UI state. Nothing is persisted, no Android permission
 * flow, no scheduler, no runtime and no backend is touched. These helpers keep
 * that statement identical everywhere instead of rewording it per screen.
 *
 * Compose mapping: PrototypeNotice, PrototypeActionResult (snackbar/inline).
 */

/** Standard closing sentence after a completed prototype interaction. */
export const DESIGN_STATE_ACTION = "Entwurfszustand, keine Runtime-Aktion ausgeführt.";

/** Used where a demo area shows example entries instead of device data. */
export const DEMO_AREA_NOTE =
  "Zustandsdemonstration der Oberfläche. Beispielwerte, keine Gerätedaten und kein Inventar.";

/** Banner for a screen whose controls are frontend specification only. */
export function PrototypeBanner({ children }: { children: ReactNode }) {
  return (
    <div className="px-4">
      <InlineNotice tone="info">{children}</InlineNotice>
    </div>
  );
}

/**
 * Polite announcement of the result of a prototype action.
 * Renders nothing until an action ran, so no screen starts with a claim.
 */
export function ActionResult({
  message,
  className,
}: {
  message: string | null;
  className?: string;
}) {
  return (
    <p
      role="status"
      aria-live="polite"
      className={cn("px-4 pt-2 text-[11px] leading-4 text-muted-foreground", className)}
    >
      {message ?? ""}
    </p>
  );
}

/**
 * Local result channel for prototype actions.
 * The message clears itself so a stale confirmation never looks like state.
 */
export function useActionResult(timeoutMs = 6000) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const report = useCallback(
    (next: string) => {
      setMessage(next);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setMessage(null), timeoutMs);
    },
    [timeoutMs],
  );

  useEffect(() => () => window.clearTimeout(timer.current), []);

  return { message, report };
}

/** Field label plus value row for compact detail sheets. */
export function DetailField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-2">
      <span className="label-system shrink-0">{label}</span>
      <span className="min-w-0 text-right text-[12px] leading-5 text-subtle-foreground">
        {children}
      </span>
    </div>
  );
}
