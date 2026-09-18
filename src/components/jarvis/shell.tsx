import type { ComponentType, ReactNode } from "react";
import { Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { JarvisWordmark } from "@/components/brand/jarvis-mark";
import { ExecutionTag, PrivacyTag, StatusTag } from "./primitives";
import { ValueTransition } from "./motion";
import { layout } from "@/lib/jarvis/tokens";
import type { ExecutionLocation, PrivacyMode, SystemState } from "@/lib/jarvis/ia";

/**
 * Locked shell primitives: top app bar, persistent runtime strip, bottom navigation.
 * Compose mapping: JarvisTopAppBar, JarvisRuntimeStrip, JarvisNavigationBar.
 */

export function TopAppBar({
  onSettings,
  settingsLabel = "Einstellungen",
  trailing,
}: {
  onSettings?: () => void;
  settingsLabel?: string;
  trailing?: ReactNode;
}) {
  return (
    <header
      className="flex shrink-0 items-center justify-between border-b border-border-soft px-4"
      style={{ height: layout.topBarHeight, paddingTop: "var(--j-safe-top)" }}
    >
      <JarvisWordmark height={12} />
      {trailing ?? (
        <button
          type="button"
          aria-label={settingsLabel}
          onClick={onSettings}
          className="j-pressable flex size-12 items-center justify-center rounded-sm"
        >
          <Settings className="size-[18px] text-muted-foreground" aria-hidden />
        </button>
      )}
    </header>
  );
}

export function RuntimeStrip({
  runtimeState,
  runtimeLabel,
  execution,
  privacy,
}: {
  runtimeState: SystemState;
  runtimeLabel: string;
  execution: ExecutionLocation;
  privacy: PrivacyMode;
}) {
  return (
    <div
      className="flex shrink-0 items-center justify-between gap-3 border-b border-border-soft bg-surface px-4 py-1.5"
      style={{ zIndex: "var(--j-z-runtime-strip)" }}
      aria-label="Laufzeitstatus"
    >
      <ValueTransition value={`${runtimeState}:${runtimeLabel}`}>
        <StatusTag state={runtimeState} label={runtimeLabel} />
      </ValueTransition>
      <span className="flex items-center gap-2">
        <ValueTransition value={execution}>
          <ExecutionTag where={execution} />
        </ValueTransition>
        <ValueTransition value={privacy}>
          <PrivacyTag mode={privacy} />
        </ValueTransition>
      </span>
    </div>
  );
}

export type NavItem<T extends string> = {
  id: T;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

export function BottomNav<T extends string>({
  items,
  current,
  onSelect,
  safeBottom = 0,
  label = "Hauptnavigation",
}: {
  items: NavItem<T>[];
  current: T;
  onSelect: (id: T) => void;
  safeBottom?: number;
  label?: string;
}) {
  const index = Math.max(
    0,
    items.findIndex((i) => i.id === current),
  );
  const columnWidth = 100 / items.length;

  return (
    <nav
      className="relative flex shrink-0 items-stretch border-t border-border-soft bg-surface"
      style={{
        height: layout.bottomNavHeight + safeBottom,
        paddingBottom: safeBottom,
        zIndex: "var(--j-z-bottom-nav)",
      }}
      aria-label={label}
    >
      {/* Selection indicator travels instead of snapping. */}
      <span
        aria-hidden
        className="pointer-events-none absolute top-1.5 flex justify-center transition-transform duration-[var(--j-duration-deliberate)] ease-[var(--j-ease-emphasized)] motion-reduce:transition-none"
        style={{
          width: `${columnWidth}%`,
          transform: `translate3d(${index * 100}%, 0, 0)`,
        }}
      >
        <span className="h-7 w-14 rounded-full bg-surface-selected" />
      </span>

      {items.map((item) => {
        const active = item.id === current;
        const Icon = item.icon;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            aria-current={active ? "page" : undefined}
            className="j-pressable relative flex flex-1 flex-col items-center justify-center gap-1 bg-transparent active:bg-transparent"
          >
            <span className="flex h-7 w-14 items-center justify-center">
              <Icon
                className={cn(
                  "size-[18px] transition-colors duration-[var(--j-duration-fast)] ease-[var(--j-ease-standard)] motion-reduce:transition-none",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              />
            </span>
            <span
              className={cn(
                "text-[11px] leading-3 transition-colors duration-[var(--j-duration-fast)] ease-[var(--j-ease-standard)] motion-reduce:transition-none",
                active ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
