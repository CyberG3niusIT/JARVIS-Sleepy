import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Reusable motion primitives.
 * Direction and duration come from the locked tokens in src/lib/jarvis/tokens.ts;
 * the CSS lives in src/styles.css so reduced motion is handled in one place.
 *
 * Compose mapping: AnimatedContent with slideInHorizontally + fadeIn.
 */

/** Directional screen transition. Forward = later destination in navigation order. */
export function ScreenTransition({
  transitionKey,
  direction,
  children,
  className,
}: {
  transitionKey: string | number;
  direction: "forward" | "back" | "none";
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      key={transitionKey}
      className={cn(
        direction === "forward" && "j-screen-forward",
        direction === "back" && "j-screen-back",
        direction === "none" && "j-fade",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Crossfades a changing value instead of letting it blink.
 * The element is keyed by the value itself, so the new value animates on the
 * same render it appears, without a delayed state update.
 */
export function ValueTransition({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span key={value} className={cn("j-value-change inline-flex", className)}>
      {children}
    </span>
  );
}

/**
 * Tracks navigation order so a tab change knows whether it moves forward or back.
 * The direction is computed during render, so the first render after a tab change
 * already carries the correct slide instead of a fade that upgrades later.
 */
export function useDirection(index: number): "forward" | "back" | "none" {
  const previous = useRef(index);
  const lastDirection = useRef<"forward" | "back" | "none">("none");

  const direction =
    index === previous.current
      ? lastDirection.current
      : index > previous.current
        ? "forward"
        : "back";

  useEffect(() => {
    previous.current = index;
    lastDirection.current = direction;
  }, [index, direction]);

  return direction;
}
