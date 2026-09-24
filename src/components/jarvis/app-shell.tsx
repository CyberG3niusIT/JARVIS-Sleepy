import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Bot,
  BrainCircuit,
  CalendarClock,
  ChevronDown,
  Command,
  Gauge,
  HardDrive,
  ListTree,
  LockKeyhole,
  MemoryStick,
  Mic,
  Minus,
  PanelLeftClose,
  Search,
  Settings,
  Shield,
  Square,
  TerminalSquare,
  Wrench,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { JarvisSnapshot, SectionId } from "@/lib/jarvis/types";
import { cn } from "@/lib/utils";
import { presentRuntimeState } from "@/lib/jarvis/runtime-status";
import { Brand, PrototypeIndicator, StatusDot } from "./primitives";

const navigation: { id: SectionId; label: string; icon: typeof Gauge }[] = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "ai-core", label: "AI Core", icon: BrainCircuit },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "voice", label: "Voice", icon: Mic },
  { id: "memory", label: "Memory", icon: MemoryStick },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "automations", label: "Automations", icon: CalendarClock },
  { id: "system", label: "System", icon: HardDrive },
  { id: "logs", label: "Logs", icon: ListTree },
  { id: "settings", label: "Einstellungen", icon: Settings },
];
export function AppShell({
  data,
  active,
  onNavigate,
  prototype,
  children,
}: {
  data: JarvisSnapshot;
  active: SectionId;
  onNavigate: (id: SectionId) => void;
  prototype: boolean;
  children: React.ReactNode;
}) {
  const runtime = presentRuntimeState(data.runtime.state);
  const runtimeText = data.runtime.detail
    ? `${runtime.label}, ${data.runtime.detail.charAt(0).toLocaleLowerCase("de-DE")}${data.runtime.detail.slice(1)}`
    : runtime.label;
  const [now, setNow] = useState<Date>();
  const [command, setCommand] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);
  const navigateFromSearch = () => {
    const normalized = command.trim().toLocaleLowerCase("de-DE");
    if (!normalized) return;
    const match = navigation.find((item) =>
      item.label.toLocaleLowerCase("de-DE").includes(normalized),
    );
    if (match) {
      onNavigate(match.id);
      setCommand("");
      searchRef.current?.blur();
    }
  };
  return (
    <div className="flex h-screen min-h-[680px] min-w-[1100px] overflow-hidden bg-background text-foreground">
      <aside className="flex w-[188px] shrink-0 flex-col border-r border-border bg-sidebar">
        <div className="flex h-16 items-center border-b border-border px-3">
          <Brand />
        </div>
        <nav className="flex-1 space-y-0.5 p-2" aria-label="Hauptnavigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={cn(
                "group flex h-8 w-full items-center gap-2 rounded-sm px-2 text-left text-[11px] text-sidebar-foreground transition-colors hover:bg-sidebar-accent",
                active === id && "bg-selection text-primary",
              )}
            >
              <Icon className="size-3.5" />
              <span>{label}</span>
              {active === id && <span className="ml-auto h-4 w-0.5 bg-primary" />}
            </button>
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <div className="flex items-center gap-2 text-[10px]">
            <StatusDot tone={runtime.tone} />
            <span>{runtime.label}</span>
          </div>
          <div className="mt-2 flex items-center justify-between text-[9px] text-muted-foreground">
            <span>{data.version}</span>
            <span>{data.build}</span>
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-11 shrink-0 items-center gap-3 border-b border-border bg-topbar px-3">
          <div className="flex min-w-32 max-w-[300px] items-center gap-2 text-[10px]">
            <StatusDot tone={runtime.tone} />
            <span className="truncate" title={runtimeText}>
              {runtimeText}
            </span>
            {prototype && <PrototypeIndicator />}
          </div>
          <div className="relative mx-auto w-full max-w-[580px]">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
            <Input
              ref={searchRef}
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") navigateFromSearch();
              }}
              className="h-8 bg-background pl-8 pr-16 text-[11px]"
              placeholder="Bereich suchen und mit Enter öffnen..."
              aria-label="Bereich suchen"
            />
            <kbd className="absolute right-2 top-2 rounded-sm border border-border bg-secondary px-1.5 py-0.5 text-[9px] text-muted-foreground">
              Strg K
            </kbd>
          </div>
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              title="PrivacyGate im Backend vorhanden, Desktop-Steuerung nicht verbunden"
              aria-label="Datenschutzsteuerung nicht verbunden"
              disabled
            >
              <Shield className="size-3.5" />
            </Button>
            <div className="px-2 text-right">
              <div className="text-[10px]">
                {now?.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) ??
                  "--:--"}
              </div>
              <div className="text-[9px] text-muted-foreground">
                {now?.toLocaleDateString("de-DE", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                }) ?? "--.--.----"}
              </div>
            </div>
            <div
              className="ml-1 flex border-l border-border pl-1 text-muted-foreground"
              aria-label="Fensterdarstellung"
            >
              <span className="flex size-8 items-center justify-center" title="Nur Darstellung">
                <Minus className="size-3" />
              </span>
              <span className="flex size-8 items-center justify-center" title="Nur Darstellung">
                <Square className="size-2.5" />
              </span>
              <span className="flex size-8 items-center justify-center" title="Nur Darstellung">
                <X className="size-3" />
              </span>
            </div>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
