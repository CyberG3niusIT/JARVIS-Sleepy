import { useState } from "react";
import {
  Home,
  MessageSquare,
  LayoutGrid,
  MoreHorizontal,
  ShieldCheck,
} from "lucide-react";
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
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import {
  BottomNav,
  RuntimeStrip,
  TopAppBar,
  type NavItem,
} from "@/components/jarvis/shell";
import { ScreenTransition, useDirection } from "@/components/jarvis/motion";
import { productAreas } from "@/lib/jarvis/ia";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Variant D: "Systemleiste + Runtime-Leiste"
 * Reference implementation of the locked design system. Information architecture
 * unchanged: bottom navigation from A, persistent runtime strip from B, no drawer,
 * composer only on the chat screen.
 */

type TabId = "start" | "chat" | "system" | "more";

const tabs: NavItem<TabId>[] = [
  { id: "start", label: "Start", icon: Home },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "system", label: "System", icon: LayoutGrid },
  { id: "more", label: "Mehr", icon: MoreHorizontal },
];

export function VariantD() {
  const [tab, setTab] = useState<TabId>("start");
  const index = tabs.findIndex((t) => t.id === tab);
  const direction = useDirection(index);

  return (
    <div className="flex h-full flex-col">
      <TopAppBar onSettings={() => setTab("more")} />

      {/* Persistent runtime strip: visible on Start, Chat, System und Mehr. */}
      <RuntimeStrip
        runtimeState="design_state"
        runtimeLabel={comparisonBaseline.labels.runtime}
        execution={comparisonBaseline.execution}
        privacy={comparisonBaseline.privacyMode}
      />

      <div className="hide-scrollbar flex-1 overflow-y-auto">
        <ScreenTransition transitionKey={tab} direction={direction} className="min-h-full">
          {tab === "start" ? <StartScreen /> : null}
          {tab === "chat" ? <ChatScreen /> : null}
          {tab === "system" ? <SystemScreen /> : null}
          {tab === "more" ? <MoreScreen /> : null}
        </ScreenTransition>
      </div>

      <BottomNav items={tabs} current={tab} onSelect={setTab} safeBottom={GESTURE_BAR} />
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
