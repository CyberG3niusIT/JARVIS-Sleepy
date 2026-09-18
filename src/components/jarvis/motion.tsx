import { useEffect, useRef, useState, type ReactNode } from "react";
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
 * Used by the runtime strip so a state change reads as a change.
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
  const first = useRef(true);
  const [key, setKey] = useState(value);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setKey(value);
  }, [value]);

  return (
    <span key={key} className={cn("j-value-change inline-flex", className)}>
      {children}
    </span>
  );
}

/** Tracks navigation order so a tab change knows whether it moves forward or back. */
export function useDirection(index: number): "forward" | "back" | "none" {
  const previous = useRef(index);
  const [direction, setDirection] = useState<"forward" | "back" | "none">("none");

  useEffect(() => {
    if (previous.current === index) return;
    setDirection(index > previous.current ? "forward" : "back");
    previous.current = index;
  }, [index]);

  return direction;
}
