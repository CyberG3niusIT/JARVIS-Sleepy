import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/jarvis/app-shell";
import {
  AiCoreSection,
  AgentsSection,
  AutomationsSection,
  DashboardSection,
  LogsSection,
  MemorySection,
  SettingsSection,
  SystemSection,
  ToolsSection,
  VoiceSection,
} from "@/components/jarvis/sections";
import { EmptyState, ErrorState, LoadingState, OfflineState } from "@/components/jarvis/primitives";
import { PrototypeModeContext } from "@/components/jarvis/mode-context";
import { useJarvis } from "@/lib/jarvis/use-jarvis";
import type { SectionId } from "@/lib/jarvis/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "J.A.R.V.I.S | Local AI Assistant" },
      {
        name: "description",
        content: "Professionelles lokales Kontrollzentrum für die JARVIS AI Runtime.",
      },
      { property: "og:title", content: "J.A.R.V.I.S | Local AI Assistant" },
      {
        property: "og:description",
        content:
          "Lokales Kontrollzentrum für Modelle, Agenten, Speicher, Werkzeuge und Systemdiagnose.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});
function Index() {
  const [active, setActive] = useState<SectionId>("dashboard");
  const { runtime, adapter, reload, execute } = useJarvis();
  if (runtime.phase === "loading")
    return (
      <div className="p-6">
        <LoadingState />
      </div>
    );
  if (runtime.phase === "offline")
    return (
      <div className="p-6">
        <OfflineState />
      </div>
    );
  if (runtime.phase === "error")
    return (
      <div className="p-6">
        <ErrorState retry={() => void reload()} />
      </div>
    );
  if (!runtime.data)
    return (
      <div className="p-6">
        <EmptyState />
      </div>
    );
  const data = runtime.data;
  const sections: Record<SectionId, React.ReactNode> = {
    dashboard: <DashboardSection data={data} />,
    "ai-core": <AiCoreSection data={data} adapter={adapter} />,
    agents: <AgentsSection data={data} adapter={adapter} />,
    voice: <VoiceSection data={data} adapter={adapter} />,
    memory: <MemorySection data={data} />,
    tools: <ToolsSection data={data} adapter={adapter} />,
    automations: <AutomationsSection data={data} adapter={adapter} />,
    system: <SystemSection data={data} adapter={adapter} onExecute={execute} />,
    logs: <LogsSection data={data} adapter={adapter} />,
    settings: <SettingsSection data={data} />,
  };
  return (
    <PrototypeModeContext.Provider value={adapter.mode === "prototype"}>
      <AppShell
        data={data}
        active={active}
        onNavigate={setActive}
        prototype={adapter.mode === "prototype"}
      >
        {sections[active]}
      </AppShell>
    </PrototypeModeContext.Provider>
  );
}
