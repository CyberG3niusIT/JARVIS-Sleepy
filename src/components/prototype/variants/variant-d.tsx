import { useState } from "react";
import {
  Home,
  MessageSquare,
  LayoutGrid,
  MoreHorizontal,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { JarvisWordmark } from "@/components/brand/jarvis-mark";
import { GESTURE_BAR, ScrollBody } from "@/components/prototype/phone-frame";
import {
  CapabilityList,
  ChatThread,
  Composer,
  NotBoundNotice,
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
import { productAreas } from "@/lib/jarvis/ia";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Variant D: "Systemleiste + Runtime-Leiste"
 * Consolidated candidate: bottom navigation from A, persistent runtime strip
 * from B. No drawer, composer only on the chat screen.
 */

const NAV_HEIGHT = 56;

type TabId = "start" | "chat" | "system" | "more";

const tabs: { id: TabId; label: string; icon: typeof Home }[] = [
  { id: "start", label: "Start", icon: Home },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "system", label: "System", icon: LayoutGrid },
  { id: "more", label: "Mehr", icon: MoreHorizontal },
];

export function VariantD() {
  const [tab, setTab] = useState<TabId>("start");

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border-soft px-4">
        <JarvisWordmark height={12} />
        <button
          type="button"
          aria-label="Einstellungen"
          onClick={() => setTab("more")}
          className="flex size-10 items-center justify-center rounded-sm"
        >
          <Settings className="size-[18px] text-muted-foreground" aria-hidden />
        </button>
      </header>

      {/* Persistent runtime strip: visible on Start, Chat, System und Mehr. */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border-soft bg-surface px-4 py-1.5">
        <StatusTag state="design_state" label={comparisonBaseline.labels.runtime} />
        <span className="flex items-center gap-2">
          <ExecutionTag where={comparisonBaseline.execution} />
          <PrivacyTag mode={comparisonBaseline.privacyMode} />
        </span>
      </div>

      <div className="hide-scrollbar flex-1 overflow-y-auto">
        {tab === "start" ? <StartScreen /> : null}
        {tab === "chat" ? <ChatScreen /> : null}
        {tab === "system" ? <SystemScreen /> : null}
        {tab === "more" ? <MoreScreen /> : null}
      </div>

      <nav
        className="flex shrink-0 items-stretch border-t border-border-soft bg-surface"
        style={{ height: NAV_HEIGHT + GESTURE_BAR, paddingBottom: GESTURE_BAR }}
        aria-label="Hauptnavigation"
      >
        {tabs.map((t) => {
          const active = t.id === tab;
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              aria-current={active ? "page" : undefined}
              className="flex flex-1 flex-col items-center justify-center gap-1"
            >
              <span
                className={cn(
                  "flex h-6 w-14 items-center justify-center rounded-full transition-colors duration-[120ms]",
                  active && "bg-surface-selected",
                )}
              >
                <Icon
                  className={cn("size-[18px]", active ? "text-primary" : "text-muted-foreground")}
                  aria-hidden
                />
              </span>
              <span
                className={cn(
                  "text-[11px] leading-3",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {t.label}
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}

function StartScreen() {
  return (
    <ScrollBody>
      <NotBoundNotice />
      <SectionHeader>Runtime</SectionHeader>
      <RuntimeSummary />
      <SectionHeader>Privacy</SectionHeader>
      <PrivacyBlock mode={comparisonBaseline.privacyMode} />
      <SectionHeader>Entscheidungsreihenfolge</SectionHeader>
      <RoutingLadderBlock limit={5} />
      <div className="px-4 py-2">
        <span className="value-mono">3 weitere Stufen unter System</span>
      </div>
    </ScrollBody>
  );
}

function ChatScreen() {
  return (
    <div className="flex min-h-full flex-col">
      <div className="flex-1">
        <ChatThread />
      </div>
      <Composer />
    </div>
  );
}

function SystemScreen() {
  return (
    <ScrollBody>
      <SectionHeader>Fähigkeiten</SectionHeader>
      <CapabilityList dense />
      <SectionHeader>Vollständige Entscheidungsreihenfolge</SectionHeader>
      <RoutingLadderBlock />
    </ScrollBody>
  );
}

function MoreScreen() {
  const secondary = productAreas.filter((a) => a.tier === "secondary");
  return (
    <ScrollBody>
      <SectionHeader>Einstellungen</SectionHeader>
      <SettingsList />
      <SectionHeader>Bereiche</SectionHeader>
      <ListGroup>
        {secondary.map((a) => (
          <ListRow
            key={a.id}
            title={a.label}
            subtitle={a.purpose}
            trailing={<StatusTag state={a.state} dot={false} />}
            chevron
            onClick={() => {}}
          />
        ))}
      </ListGroup>
      <div className="flex items-center gap-2 px-4 py-4 text-muted-foreground">
        <ShieldCheck className="size-4" aria-hidden />
        <span className="text-[11px]">Alle Bereiche laufen lokal, sofern nicht anders markiert.</span>
      </div>
    </ScrollBody>
  );
}
