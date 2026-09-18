import { useState } from "react";
import { ChevronUp, ChevronDown, Settings, Sliders } from "lucide-react";
import { cn } from "@/lib/utils";
import { JarvisSymbol } from "@/components/brand/jarvis-mark";
import { GESTURE_BAR } from "@/components/prototype/phone-frame";
import {
  CapabilityList,
  ChatThread,
  Composer,
  PrivacyBlock,
  RoutingLadderBlock,
  RuntimeSummary,
  SettingsList,
} from "@/components/jarvis/blocks";
import {
  ExecutionTag,
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { moreDestinations } from "@/lib/jarvis/ia";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Variant C — "Konversation + Systemblatt"
 * Axis: conversation is the root surface; the whole system lives in one
 * expandable bottom sheet. No tab bar, no drawer — one gesture between
 * talking to JARVIS and inspecting/controlling the runtime.
 */

type SheetState = "peek" | "expanded";
type SheetTab = "runtime" | "capabilities" | "settings";

export function VariantC() {
  const [sheet, setSheet] = useState<SheetState>("peek");
  const [tab, setTab] = useState<SheetTab>("runtime");

  const peekHeight = 44 + GESTURE_BAR + 52; // handle strip + gesture inset + composer

  return (
    <div className="relative flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border-soft px-4">
        <span className="flex items-center gap-2">
          <JarvisSymbol size={18} />
          <span className="text-[15px] font-medium text-foreground">Chat</span>
        </span>
        <span className="flex items-center gap-3">
          <PrivacyTag mode={comparisonBaseline.privacyMode} />
          <Settings className="size-[18px] text-muted-foreground" aria-hidden />
        </span>
      </header>

      <div
        className="hide-scrollbar flex-1 overflow-y-auto"
        style={{ paddingBottom: peekHeight }}
      >
        <ChatThread full />
      </div>

      {/* Composer sits above the system sheet; keyboard would push both. */}
      <div
        className="absolute inset-x-0 z-10"
        style={{ bottom: 44 + GESTURE_BAR }}
      >
        <Composer hint="Lokal fragen, Antwort bleibt auf dem Gerät" />
      </div>

      <SystemSheet
        state={sheet}
        tab={tab}
        onTab={setTab}
        onToggle={() => setSheet(sheet === "peek" ? "expanded" : "peek")}
      />
    </div>
  );
}

function SystemSheet({
  state,
  tab,
  onTab,
  onToggle,
}: {
  state: SheetState;
  tab: SheetTab;
  onTab: (t: SheetTab) => void;
  onToggle: () => void;
}) {
  const expanded = state === "expanded";
  const tabs: { id: SheetTab; label: string }[] = [
    { id: "runtime", label: "Runtime" },
    { id: "capabilities", label: "Fähigkeiten" },
    { id: "settings", label: "System" },
  ];

  return (
    <div
      className={cn(
        "absolute inset-x-0 bottom-0 z-20 flex flex-col border-t border-border bg-surface",
        "transition-[height] duration-200 ease-out",
      )}
      style={{ height: expanded ? 620 : 44 + GESTURE_BAR }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex h-11 shrink-0 items-center gap-3 px-4"
      >
        <Sliders className="size-4 text-muted-foreground" aria-hidden />
        <span className="flex-1 text-left text-[12px] text-subtle-foreground">
          System
        </span>
        <StatusTag
          state="design_state"
          label={comparisonBaseline.labels.runtime}
          dot={false}
        />
        <ExecutionTag where={comparisonBaseline.execution} />
        {expanded ? (
          <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronUp className="size-4 text-muted-foreground" aria-hidden />
        )}
      </button>

      {expanded ? (
        <>
          <div className="flex shrink-0 border-b border-border-soft px-2">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onTab(t.id)}
                aria-current={t.id === tab ? "true" : undefined}
                className={cn(
                  "touch-row flex-1 border-b-2 px-2 text-[12px]",
                  t.id === tab
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div
            className="hide-scrollbar flex-1 overflow-y-auto"
            style={{ paddingBottom: GESTURE_BAR }}
          >
            {tab === "runtime" ? (
              <>
                <SectionHeader>Laufzeit</SectionHeader>
                <RuntimeSummary compact />
                <SectionHeader>Privacy</SectionHeader>
                <PrivacyBlock mode={comparisonBaseline.privacyMode} />
                <SectionHeader>Entscheidungsreihenfolge</SectionHeader>
                <RoutingLadderBlock limit={6} />
              </>
            ) : null}
            {tab === "capabilities" ? (
              <>
                <SectionHeader>Fähigkeiten</SectionHeader>
                <CapabilityList />
              </>
            ) : null}
            {tab === "settings" ? (
              <>
                <SectionHeader>Bereiche</SectionHeader>
                <ListGroup>
                  {moreDestinations
                    .map((a) => (
                      <ListRow
                        key={a.id}
                        title={a.label}
                        trailing={<StatusTag state={a.state} dot={false} />}
                        chevron
                        onClick={() => {}}
                      />
                    ))}
                </ListGroup>
                <SectionHeader>Einstellungen</SectionHeader>
                <SettingsList />
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}
