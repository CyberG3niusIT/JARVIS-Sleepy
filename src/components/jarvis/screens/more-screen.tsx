import { useEffect, useRef, useState, type ReactNode } from "react";
import { ShieldCheck } from "lucide-react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { ScreenTransition, SectionEnter } from "@/components/jarvis/motion";
import { VoiceScreen } from "@/components/jarvis/screens/voice-screen";
import { MemoryScreen } from "@/components/jarvis/screens/memory-screen";
import { AutomationsScreen } from "@/components/jarvis/screens/automations-screen";
import { SettingsScreen } from "@/components/jarvis/screens/settings-screen";
import { AboutScreen } from "@/components/jarvis/screens/about-screen";
import type { DetailScreenProps } from "@/components/jarvis/screens/detail-header";
import { moreDestinations, type AreaId } from "@/lib/jarvis/ia";

/**
 * Mehr: secondary user areas and product settings (Phase 5).
 *
 * Mirrors the System container: one typed detail state, one screen map, one
 * place for navigation logic, so no row can carry a dead chevron. The order of
 * the overview comes from the locked Phase 4 information architecture.
 *
 * Compose mapping: MoreScreen(state, onBack), MoreAreaRow.
 */

/** The five locked Mehr destinations. */
type MoreAreaId = "voice" | "memory" | "automations" | "settings" | "about";

const detailScreens: Record<MoreAreaId, (props: DetailScreenProps) => ReactNode> = {
  voice: VoiceScreen,
  memory: MemoryScreen,
  automations: AutomationsScreen,
  settings: SettingsScreen,
  about: AboutScreen,
};

function isMoreArea(id: AreaId): id is MoreAreaId {
  return id in detailScreens;
}

/**
 * The settings gear raises a counter instead of a flag, so a repeated tap
 * reopens Einstellungen even when the Mehr tab is already active.
 */
export function MoreScreen({ settingsIntent = 0 }: { settingsIntent?: number }) {
  const [detail, setDetail] = useState<MoreAreaId | null>(
    settingsIntent > 0 ? "settings" : null,
  );
  /**
   * Direction of the last nested step. The first render shows the overview
   * without a slide; the tab switch itself already carries that motion. The
   * component unmounts when the Mehr tab is left, so a later return starts on
   * the overview again with direction "none".
   */
  const [direction, setDirection] = useState<"forward" | "back" | "none">("none");
  const lastIntent = useRef(settingsIntent);

  useEffect(() => {
    if (settingsIntent === lastIntent.current) return;
    lastIntent.current = settingsIntent;
    if (settingsIntent > 0) {
      setDirection("forward");
      setDetail("settings");
    }
  }, [settingsIntent]);

  const openArea = (area: AreaId) => {
    if (!isMoreArea(area)) return;
    setDirection("forward");
    setDetail(area);
  };

  const closeDetail = () => {
    setDirection("back");
    setDetail(null);
  };

  const Detail = detail ? detailScreens[detail] : null;

  return (
    <ScreenTransition
      transitionKey={detail ?? "overview"}
      direction={direction}
      className="min-h-full"
    >
      {Detail ? <Detail onBack={closeDetail} /> : <MoreOverview onOpenArea={openArea} />}
    </ScreenTransition>
  );
}

function MoreOverview({ onOpenArea }: { onOpenArea: (area: AreaId) => void }) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <div className="border-b border-border-soft bg-surface px-4 py-4">
          <h1 className="text-[15px] leading-5 text-foreground">Mehr</h1>
          <p className="mt-1 text-[13px] leading-5 text-subtle-foreground">
            Nutzerbereiche und Produkteinstellungen
          </p>
        </div>
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Bereiche</SectionHeader>
        <ListGroup>
          {moreDestinations.map((area) => (
            <ListRow
              key={area.id}
              title={area.label}
              subtitle={area.purpose}
              trailing={<StatusTag state={area.state} dot={false} />}
              chevron
              onClick={() => onOpenArea(area.id)}
            />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <div className="flex items-center gap-2 px-4 py-4 text-muted-foreground">
          <ShieldCheck className="size-4" aria-hidden />
          <span className="text-[11px]">
            Alle Bereiche laufen lokal, sofern nicht anders markiert.
          </span>
        </div>
      </SectionEnter>
    </ScrollBody>
  );
}
