import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Android device frame for the prototype harness only.
 * 393 x 852 dp (Pixel-class baseline from Brand Spec §9).
 * Insets are real: 28 dp status bar, 24 dp gesture navigation area.
 * Nothing inside the frame may assume desktop width.
 */

export const STATUS_BAR = 28;
export const GESTURE_BAR = 24;

export function PhoneFrame({
  children,
  caption,
}: {
  children: ReactNode;
  caption?: string;
}) {
  return (
    <div className="flex w-full max-w-[393px] flex-col items-center gap-3">
      {/*
        393 dp stays the reference width. On narrower browser windows the frame
        shrinks so the page never scrolls horizontally, the product UI reflows
        at the smaller width instead of being scaled.
      */}
      <div
        className="relative w-full overflow-hidden rounded-[28px] border border-border bg-background shadow-[0_24px_60px_-24px_rgba(0,0,0,0.8)]"
        style={{ maxWidth: 393, height: 852 }}
      >
        <StatusBar />
        <div
          className="hide-scrollbar relative overflow-y-auto"
          style={{ height: 852 - STATUS_BAR }}
        >
          {children}
        </div>
        <GestureBar />
      </div>
      {caption ? (
        <p className="value-mono text-muted-foreground">{caption}</p>
      ) : null}
    </div>
  );
}

function StatusBar() {
  return (
    <div
      className="flex items-center justify-between bg-background px-5 text-[11px] text-subtle-foreground"
      style={{ height: STATUS_BAR }}
      aria-hidden
    >
      <span className="font-medium">9:41</span>
      <span className="flex items-center gap-1.5">
        <SignalGlyph />
        <BatteryGlyph />
      </span>
    </div>
  );
}

function GestureBar() {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-center"
      style={{ height: GESTURE_BAR }}
      aria-hidden
    >
      <span className="h-[3px] w-[108px] rounded-full bg-subtle-foreground/50" />
    </div>
  );
}

function SignalGlyph() {
  return (
    <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
      <rect x="0" y="6" width="2.5" height="4" rx="0.5" fill="currentColor" />
      <rect x="3.8" y="4" width="2.5" height="6" rx="0.5" fill="currentColor" />
      <rect x="7.6" y="2" width="2.5" height="8" rx="0.5" fill="currentColor" />
      <rect x="11.4" y="0" width="2.5" height="10" rx="0.5" fill="currentColor" />
    </svg>
  );
}

function BatteryGlyph() {
  return (
    <svg width="20" height="10" viewBox="0 0 20 10" fill="none">
      <rect
        x="0.5"
        y="0.5"
        width="16"
        height="9"
        rx="2"
        stroke="currentColor"
        strokeOpacity="0.6"
      />
      <rect x="2" y="2" width="11" height="6" rx="1" fill="currentColor" />
      <rect x="18" y="3.5" width="1.5" height="3" rx="0.75" fill="currentColor" />
    </svg>
  );
}

/** Content padding helper honouring the gesture inset. */
export function ScrollBody({
  children,
  className,
  extraBottom = 0,
}: {
  children: ReactNode;
  className?: string;
  extraBottom?: number;
}) {
  return (
    <div className={cn(className)} style={{ paddingBottom: GESTURE_BAR + extraBottom }}>
      {children}
    </div>
  );
}
