import { useState } from "react";
import { Home, MessageSquare, LayoutGrid, MoreHorizontal } from "lucide-react";
import { GESTURE_BAR } from "@/components/prototype/phone-frame";
import { StartScreen } from "@/components/jarvis/screens/start-screen";
import { ChatScreen } from "@/components/jarvis/screens/chat-screen";
import { SystemScreen } from "@/components/jarvis/screens/system-screen";
import { MoreScreen } from "@/components/jarvis/screens/more-screen";
import {
  BottomNav,
  RuntimeStrip,
  TopAppBar,
  type NavItem,
} from "@/components/jarvis/shell";
import { ScreenTransition, useDirection } from "@/components/jarvis/motion";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Variant D: "Systemleiste + Runtime-Leiste"
 * Reference implementation of the locked design system and of the locked Phase 4
 * information architecture: bottom navigation from A, persistent runtime strip
 * from B, no drawer, composer only on the chat screen.
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
  /**
   * Counter instead of a flag: every gear tap raises it, so Einstellungen also
   * opens when the Mehr tab is already active. Leaving Mehr resets it, so a
   * later return starts on the Mehr overview.
   */
  const [settingsIntent, setSettingsIntent] = useState(0);
  const index = tabs.findIndex((t) => t.id === tab);
  const direction = useDirection(index);

  const selectTab = (next: TabId) => {
    setSettingsIntent(0);
    setTab(next);
  };

  return (
    <div className="flex h-full flex-col">
      <TopAppBar
        onSettings={() => {
          setSettingsIntent((n) => n + 1);
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
          {tab === "start" ? (
            <StartScreen
              onOpenChat={() => selectTab("chat")}
              onOpenSystem={() => selectTab("system")}
            />
          ) : null}
          {tab === "chat" ? <ChatScreen /> : null}
          {tab === "system" ? <SystemScreen /> : null}
          {tab === "more" ? <MoreScreen settingsIntent={settingsIntent} /> : null}
        </ScreenTransition>
      </div>

      <BottomNav items={tabs} current={tab} onSelect={selectTab} safeBottom={GESTURE_BAR} />
    </div>
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
      {focusSettings ? settingsBlock : null}
      {areaList}
      <div className="flex items-center gap-2 px-4 py-4 text-muted-foreground">
        <ShieldCheck className="size-4" aria-hidden />
        <span className="text-[11px]">Alle Bereiche laufen lokal, sofern nicht anders markiert.</span>
      </div>
    </ScrollBody>
  );
}
