import { useState } from "react";
import { Menu, X, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { JarvisSymbol, JarvisWordmark } from "@/components/brand/jarvis-mark";
import { GESTURE_BAR, ScrollBody } from "@/components/prototype/phone-frame";
import {
  CapabilityList,
  ChatThread,
  Composer,
  NotBoundNotice,
  PrivacyBlock,
  RoutingLadderBlock,
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
import { areasInGroup, type AreaGroup } from "@/lib/jarvis/ia";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Variant B — "Konsole"
 * Axis: no bottom navigation. One dense console surface with an always-present
 * runtime strip and a full modal navigation drawer holding every area.
 * Highest information density; closest to Android developer/system tooling.
 */

type Screen = "console" | "chat" | "capabilities" | "settings";

export function VariantB() {
  const [screen, setScreen] = useState<Screen>("console");
  const [drawer, setDrawer] = useState(false);

  const title =
    screen === "console"
      ? "Runtime"
      : screen === "chat"
        ? "Chat"
        : screen === "capabilities"
          ? "Fähigkeiten"
          : "Einstellungen";

  return (
    <div className="relative flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border-soft px-3">
        <button
          type="button"
          aria-label="Bereiche öffnen"
          onClick={() => setDrawer(true)}
          className="flex size-10 items-center justify-center rounded-sm"
        >
          <Menu className="size-[18px] text-subtle-foreground" aria-hidden />
        </button>
        <span className="flex-1 text-[15px] font-medium text-foreground">{title}</span>
        <JarvisSymbol size={18} />
      </header>

      {/* Persistent runtime strip — visible on every screen. */}
      <div className="flex shrink-0 items-center justify-between border-b border-border-soft bg-surface px-4 py-1.5">
        <span className="flex items-center gap-2">
          <StatusTag state="design_state" label={comparisonBaseline.labels.runtime} />
        </span>
        <span className="flex items-center gap-2">
          <ExecutionTag where={comparisonBaseline.execution} />
          <PrivacyTag mode={comparisonBaseline.privacyMode} />
        </span>
      </div>

      <div className="hide-scrollbar flex-1 overflow-y-auto">
        {screen === "console" ? <ConsoleScreen onOpen={setScreen} /> : null}
        {screen === "chat" ? (
          <div className="flex min-h-full flex-col">
            <div className="flex-1">
              <ChatThread />
            </div>
          </div>
        ) : null}
        {screen === "capabilities" ? (
          <ScrollBody extraBottom={52}>
            <SectionHeader>Fähigkeiten</SectionHeader>
            <CapabilityList dense />
            <SectionHeader>Entscheidungsreihenfolge</SectionHeader>
            <RoutingLadderBlock />
          </ScrollBody>
        ) : null}
        {screen === "settings" ? (
          <ScrollBody extraBottom={52}>
            <SectionHeader>Einstellungen</SectionHeader>
            <SettingsList />
          </ScrollBody>
        ) : null}
      </div>

      {/* Docked composer: chat is reachable from every screen. */}
      <div style={{ paddingBottom: GESTURE_BAR }} className="shrink-0 bg-background">
        <Composer
          hint={screen === "chat" ? "Lokal fragen" : "Lokal fragen, Chat öffnen"}
          fieldLabel="Chat öffnen"
          onFocusField={() => setScreen("chat")}
        />
      </div>

      {drawer ? <Drawer onClose={() => setDrawer(false)} onSelect={setScreen} /> : null}
    </div>
  );
}

function ConsoleScreen({ onOpen }: { onOpen: (s: Screen) => void }) {
  return (
    <ScrollBody extraBottom={52}>
      <NotBoundNotice />
      <SectionHeader>Laufzeit</SectionHeader>
      <div className="divide-y divide-border-soft border-y border-border-soft bg-surface">
        {[
          ["Lokales Modell", comparisonBaseline.labels.localModel],
          ["Modell-Runtime", comparisonBaseline.labels.modelRuntime],
          ["Ausführungsort", comparisonBaseline.labels.execution],
          ["Sleepy-Runtime", comparisonBaseline.labels.sleepy],
          ["Sleepy-Handoff", comparisonBaseline.labels.sleepyHandoff],
          ["Cloud", comparisonBaseline.labels.cloud],
          ["Hintergrunddienst", comparisonBaseline.labels.backgroundService],
          ["Berechtigungen", comparisonBaseline.labels.permissions],
        ].map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-4 px-4 py-2">
            <span className="text-[12px] leading-4 text-subtle-foreground">{k}</span>
            <span className="value-mono text-right">{v}</span>
          </div>
        ))}
      </div>

      <SectionHeader
        action={
          <button
            type="button"
            className="flex items-center gap-1 text-[11px] text-primary"
            onClick={() => onOpen("capabilities")}
          >
            Alle <ArrowRight className="size-3" aria-hidden />
          </button>
        }
      >
        Fähigkeiten
      </SectionHeader>
      <CapabilityList dense />

      <SectionHeader>Privacy</SectionHeader>
      <PrivacyBlock mode={comparisonBaseline.privacyMode} />
    </ScrollBody>
  );
}

function Drawer({
  onClose,
  onSelect,
}: {
  onClose: () => void;
  onSelect: (s: Screen) => void;
}) {
  const groups: { label: string; group: AreaGroup }[] = [
    { label: "System", group: "system" },
    { label: "Mehr", group: "more" },
  ];
  const target: Partial<Record<string, Screen>> = {
    start: "console",
    chat: "chat",
    capabilities: "capabilities",
    settings: "settings",
  };

  return (
    <div className="absolute inset-0 z-20 flex">
      <div
        className="absolute inset-0 bg-background/80"
        onClick={onClose}
        aria-hidden
      />
      <div className="relative flex h-full w-[300px] flex-col border-r border-border bg-surface">
        <div className="flex h-14 items-center justify-between px-4">
          <JarvisWordmark height={12} />
          <button
            type="button"
            aria-label="Schließen"
            onClick={onClose}
            className="flex size-10 items-center justify-center"
          >
            <X className="size-[18px] text-muted-foreground" aria-hidden />
          </button>
        </div>
        <div className="hide-scrollbar flex-1 overflow-y-auto" style={{ paddingBottom: GESTURE_BAR }}>
          {groups.map((g) => (
            <div key={g.group}>
              <SectionHeader>{g.label}</SectionHeader>
              <ListGroup>
                {areasInGroup(g.group)
                  .map((a) => (
                    <ListRow
                      key={a.id}
                      title={a.label}
                      subtitle={a.purpose}
                      trailing={<StatusTag state={a.state} dot={false} />}
                      onClick={() => {
                        const t = target[a.id];
                        if (t) onSelect(t);
                        onClose();
                      }}
                      className={cn(!target[a.id] && "opacity-70")}
                    />
                  ))}
              </ListGroup>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
