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
import { moreDestinations, systemDestinations } from "@/lib/jarvis/ia";
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
  const [focusSettings, setFocusSettings] = useState(false);
  const index = tabs.findIndex((t) => t.id === tab);
  const direction = useDirection(index);

  const selectTab = (next: TabId) => {
    setFocusSettings(false);
    setTab(next);
  };

  return (
    <div className="flex h-full flex-col">
      <TopAppBar
        onSettings={() => {
          setFocusSettings(true);
          setTab("more");
        }}
      />

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
          {tab === "more" ? <MoreScreen focusSettings={focusSettings} /> : null}
        </ScreenTransition>
      </div>

      <BottomNav items={tabs} current={tab} onSelect={selectTab} safeBottom={GESTURE_BAR} />
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

/** System: technisches Kontrollzentrum, feste Reihenfolge der Ziele. */
function SystemScreen() {
  return (
    <ScrollBody>
      <SectionHeader>Kontrollzentrum</SectionHeader>
      <ListGroup>
        {systemDestinations.map((a) => (
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
      <SectionHeader>Vollständige Entscheidungsreihenfolge</SectionHeader>
      <RoutingLadderBlock />
    </ScrollBody>
  );
}

/** Mehr: sekundäre Nutzerbereiche und Produkteinstellungen, feste Reihenfolge. */
function MoreScreen({ focusSettings = false }: { focusSettings?: boolean }) {
  const areaList = (
    <>
      <SectionHeader>Bereiche</SectionHeader>
      <ListGroup>
        {moreDestinations.map((a) => (
          <ListRow
            key={a.id}
            title={a.label}
            subtitle={a.purpose}
            trailing={<StatusTag state={a.state} dot={false} />}
            selected={focusSettings && a.id === "settings"}
            chevron
            onClick={() => {}}
          />
        ))}
      </ListGroup>
    </>
  );

  const settingsBlock = (
    <>
      <SectionHeader>Einstellungen</SectionHeader>
      <SettingsList />
    </>
  );

  return (
    <ScrollBody>
      {focusSettings ? settingsBlock : areaList}
      {focusSettings ? areaList : settingsBlock}
      <div className="flex items-center gap-2 px-4 py-4 text-muted-foreground">
        <ShieldCheck className="size-4" aria-hidden />
        <span className="text-[11px]">Alle Bereiche laufen lokal, sofern nicht anders markiert.</span>
      </div>
    </ScrollBody>
  );
}
