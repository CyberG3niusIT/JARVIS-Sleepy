import { useMemo, useState } from "react";
import { ChevronRight, Download, Pause, Play, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { presentRuntimeState } from "@/lib/jarvis/runtime-status";
import type {
  Activity as LogItem,
  Agent,
  Automation,
  AdapterResult,
  Capability,
  JarvisAdapter,
  JarvisSnapshot,
  MemoryItem,
  Metric,
  ToolItem,
} from "@/lib/jarvis/types";
import { DataTable, type Column } from "./data-table";
import { usePrototype } from "./mode-context";
import { PerformanceChart } from "./charts";
import {
  DetailPanel,
  DetailRow,
  MetricCard,
  NotImplementedState,
  Panel,
  PrototypeIndicator,
  SectionHeader,
  StatusBadge,
  StatusDot,
} from "./primitives";

function UnsupportedAction({
  adapter,
  capability,
  children,
}: {
  adapter: JarvisAdapter;
  capability: Parameters<JarvisAdapter["hasCapability"]>[0];
  children: string;
}) {
  const supported = adapter.hasCapability(capability);
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" variant="outline" disabled={!supported}>
        {children}
      </Button>
      {!supported && <NotImplementedState compact />}
    </div>
  );
}
function SummaryGrid({ metrics, count = 4 }: { metrics: Metric[]; count?: number }) {
  return (
    <div
      className={cn(
        "grid gap-2",
        count === 6 ? "grid-cols-3 xl:grid-cols-6" : "grid-cols-2 xl:grid-cols-4",
      )}
    >
      {metrics.slice(0, count).map((metric) => (
        <MetricCard key={metric.label} metric={metric} />
      ))}
    </div>
  );
}
function KeyValueList({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <div className="divide-y divide-border">
      {rows.map((row) => (
        <div
          key={row.label}
          className="flex min-h-8 items-center justify-between gap-3 px-3 py-1.5 text-[11px]"
        >
          <span className="text-muted-foreground">{row.label}</span>
          <span className="text-right text-foreground">{row.value}</span>
        </div>
      ))}
    </div>
  );
}
function ActivityFeed({ rows, limit = 6 }: { rows: LogItem[]; limit?: number }) {
  return (
    <div className="divide-y divide-border">
      {rows.slice(0, limit).map((row) => (
        <div key={row.id} className="grid grid-cols-[52px_8px_1fr] gap-2 px-3 py-2 text-[10px]">
          <span className="font-mono text-muted-foreground">{row.time}</span>
          <StatusDot
            tone={row.level === "Fehler" ? "error" : row.level === "Warnung" ? "warning" : "info"}
          />
          <div>
            <div>{row.message}</div>
            <div className="mt-0.5 text-muted-foreground">
              {row.source} · {row.context}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
const unavailable = "Keine Live-Daten";
const serviceOf = (data: JarvisSnapshot, name: string) =>
  data.services.find((service) => service.name === name && service.health !== undefined);
const num = (value: number | null) => (value === null ? unavailable : String(value));
const dec = (value: number | null) =>
  value === null ? unavailable : String(value).replace(".", ",");

export function DashboardSection({ data }: { data: JarvisSnapshot }) {
  const prototype = usePrototype();
  // Offline dot only for the static prototype; production has no source that says "offline".
  const offlineTone = prototype ? ({ tone: "offline" } as const) : {};
  const overview: Metric[] = [
    {
      label: "AI Core",
      value: data.model.name,
      detail: `${data.model.runtime} · ${data.model.context}`,
      tone: data.model.status,
    },
    {
      label: "Voice",
      value: prototype ? "Nicht verbunden" : unavailable,
      detail: prototype ? `${data.voice.sttBackend} · ${data.voice.tts}` : unavailable,
      ...offlineTone,
    },
    {
      label: "Memory",
      value: prototype
        ? "Konfiguriert"
        : data.memoryCounts?.facts != null
          ? `${data.memoryCounts.facts} Fakten`
          : unavailable,
      detail: prototype
        ? data.memoryArchitecture.stores.join(", ")
        : data.memoryCounts?.facts != null
          ? data.memoryCounts.vectors != null
            ? `${data.memoryCounts.vectors} FAISS-Vektoren`
            : "Keine FAISS-Angabe"
          : "Keine Zähler verfügbar",
      ...(prototype
        ? { tone: "info" as const }
        : data.memoryCounts?.facts != null
          ? { tone: "online" as const }
          : {}),
    },
    {
      label: "Agenten",
      value: prototype ? `${data.agents.length} Beispiele` : unavailable,
      detail: "Keine Live-Verbindung",
      ...offlineTone,
    },
    {
      label: "Werkzeuge",
      value: prototype ? `${data.tools.length} Beispiele` : unavailable,
      detail: "Keine Live-Verbindung",
      ...offlineTone,
    },
    {
      label: "System",
      value: prototype ? "Nicht verbunden" : unavailable,
      detail: prototype ? `${data.platform.host} · ${data.platform.linuxRuntime}` : unavailable,
      ...offlineTone,
    },
  ];
  return (
    <>
      <SectionHeader
        title="Dashboard"
        description={
          prototype
            ? "Lokale Konfiguration und Prototypübersicht"
            : "Live-Zustand der JARVIS-Runtime"
        }
      />
      <div className="space-y-2 p-3">
        <div className="grid grid-cols-[minmax(0,1.15fr)_minmax(260px,.75fr)] gap-2">
          <div className="space-y-2">
            <div className="grid grid-cols-3 gap-2">
              {overview.map((m) => (
                <MetricCard key={m.label} metric={m} />
              ))}
            </div>
            <div className="grid grid-cols-[1.6fr_1fr] gap-2">
              <Panel title="Modellleistung">
                <PerformanceChart data={data.performance} secondary />
              </Panel>
              <Panel title="Systemressourcen">
                <div className="grid grid-cols-2 gap-px bg-border">
                  {data.metrics.slice(0, 4).map((m) => (
                    <div key={m.label} className="bg-card p-3">
                      <div className="flex justify-between text-[10px]">
                        <span className="text-muted-foreground">{m.label}</span>
                        <span>{m.value}</span>
                      </div>
                      <div className="mt-2 text-[9px] text-muted-foreground">{m.detail}</div>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          </div>
          <Panel
            title="Aktivitätsprotokoll"
            action={
              prototype ? (
                <div className="flex items-center gap-2">
                  <PrototypeIndicator />
                  <span className="text-[10px] text-muted-foreground">Beispiele</span>
                </div>
              ) : (
                <span className="text-[10px] text-muted-foreground">Watchdog</span>
              )
            }
          >
            <ActivityFeed rows={data.activities} limit={9} />
          </Panel>
        </div>
        <SummaryGrid metrics={data.metrics} count={6} />
      </div>
    </>
  );
}

export function AiCoreSection({ data, adapter }: { data: JarvisSnapshot; adapter: JarvisAdapter }) {
  const prototype = usePrototype();
  const [prompt, setPrompt] = useState("");
  const parameters = [
    { label: "Batchgröße", value: num(data.model.batchSize) },
    { label: "Ubatch-Größe", value: num(data.model.ubatchSize) },
    { label: "Temperatur", value: dec(data.model.temperature) },
    { label: "Top P", value: dec(data.model.topP) },
    { label: "Top K", value: num(data.model.topK) },
    {
      label: "Tool Calling",
      value:
        data.model.toolCalling === null
          ? unavailable
          : data.model.toolCalling
            ? "Aktiviert"
            : "Deaktiviert",
    },
  ];
  return (
    <>
      <SectionHeader
        title="AI Core"
        description={
          prototype
            ? "Modellkonfiguration und nicht verbundene Runtime"
            : "Modell und Dienst-Erreichbarkeit laut Backend"
        }
      />
      <Tabs defaultValue="modell" className="p-3">
        <TabsList>
          <TabsTrigger value="modell">Modell</TabsTrigger>
          <TabsTrigger value="inferenz">Inferenz</TabsTrigger>
          <TabsTrigger value="hardware">Hardware</TabsTrigger>
          <TabsTrigger value="erweitert">Erweitert</TabsTrigger>
        </TabsList>
        <TabsContent value="modell" className="mt-2 space-y-2">
          <div className="grid grid-cols-[1fr_1.3fr_300px] gap-2">
            <Panel title={prototype ? "Konfiguriertes Modell" : "Geladenes Modell"}>
              <KeyValueList
                rows={[
                  { label: "Modell", value: data.model.name },
                  { label: "Runtime", value: data.model.runtime },
                  { label: "Quantisierung", value: data.model.quantization },
                  { label: "Kontext", value: data.model.context },
                  { label: "Endpoint", value: data.model.endpoint },
                ]}
              />
            </Panel>
            <Panel title="Inferenzdurchsatz und Latenz">
              <PerformanceChart data={data.performance} secondary unit="" />
            </Panel>
            <DetailPanel title="Status">
              <DetailRow
                label="Health"
                value={
                  <StatusBadge
                    tone={serviceOf(data, "Main LLM")?.health ?? "offline"}
                    label={serviceOf(data, "Main LLM")?.configuration ?? "Nicht verbunden"}
                  />
                }
              />
              <DetailRow label="Konfiguration" value={prototype ? "Vorhanden" : unavailable} />
              <DetailRow label="Kontextlast" value={unavailable} />
              <DetailRow label="Warteschlange" value={unavailable} />
              {data.llmStats && (
                <>
                  <DetailRow
                    label={`Anfragen (${data.llmStats.hours} h)`}
                    value={String(data.llmStats.interactions)}
                  />
                  <DetailRow
                    label="Ø Latenz"
                    value={
                      data.llmStats.avgLatencyMs === null
                        ? unavailable
                        : `${data.llmStats.avgLatencyMs.toLocaleString("de-DE")} ms`
                    }
                  />
                </>
              )}
              <UnsupportedAction adapter={adapter} capability="agent.configure">
                Modell konfigurieren
              </UnsupportedAction>
            </DetailPanel>
          </div>
          <div className="grid grid-cols-[1.4fr_1fr] gap-2">
            <Panel title="Schnelleingabe">
              <div className="flex gap-2 p-3">
                <Input
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Prompt für verbundene Runtime..."
                />
                <Button disabled={!prompt.trim() || !adapter.hasCapability("llm.prompt")}>
                  Senden
                </Button>
              </div>
              <div className="px-3 pb-3">
                <NotImplementedState compact />
              </div>
            </Panel>
            <Panel title="Hardware">
              <KeyValueList
                rows={[
                  { label: "GPU", value: data.hardware.gpu },
                  { label: "VRAM", value: `Kapazität: ${data.hardware.vramCapacity}` },
                  { label: "GPU-Layer", value: num(data.model.gpuLayers) },
                ]}
              />
            </Panel>
          </div>
          <Panel title={prototype ? "Beispielereignisse" : "Ereignisse"}>
            <ActivityFeed rows={data.activities.filter((a) => a.source === "AI Core")} limit={4} />
          </Panel>
        </TabsContent>
        {["inferenz", "hardware", "erweitert"].map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-2">
            <div className="grid grid-cols-2 gap-2">
              <Panel title={tab === "hardware" ? "GPU-Auslastung" : "Inferenzprofil"}>
                <PerformanceChart
                  data={tab === "hardware" ? data.gpuPerformance : data.performance}
                  secondary
                />
              </Panel>
              <Panel title={prototype ? "Konfigurierte Parameter" : "Parameter"}>
                <KeyValueList rows={parameters} />
              </Panel>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}

export function AgentsSection({ data, adapter }: { data: JarvisSnapshot; adapter: JarvisAdapter }) {
  const prototype = usePrototype();
  const offlineTone = prototype ? ({ tone: "offline" } as const) : {};
  const [selected, setSelected] = useState(data.agents[0]);
  const cols: Column<Agent>[] = [
    { key: "name", label: "Name", render: (a) => <span className="font-medium">{a.name}</span> },
    { key: "role", label: "Rolle", render: (a) => a.role },
    {
      key: "status",
      label: "Status",
      render: (a) => <StatusBadge tone={a.status} label="Nicht verbunden" />,
    },
    { key: "model", label: "Modell", render: (a) => a.model },
    { key: "last", label: "Letzte Aktivität", render: (a) => a.lastActivity },
    { key: "tasks", label: "Laufende Aufgaben", render: (a) => a.tasks },
  ];
  return (
    <>
      <SectionHeader
        title="Agents"
        description={
          prototype
            ? "Prototyp-Fixtures für Auswahl und Detailansichten"
            : "Keine Agenten-Schnittstelle im Backend"
        }
      />
      <div className="space-y-2 p-3">
        <SummaryGrid
          metrics={[
            { label: prototype ? "Beispielzeilen" : "Einträge", value: String(data.agents.length) },
            { label: "Live verbunden", value: prototype ? "0" : unavailable, tone: "offline" },
            { label: "Laufende Aufgaben", value: unavailable },
            {
              label: "Runtime",
              value: prototype ? "Nicht verbunden" : unavailable,
              ...offlineTone,
            },
          ]}
        />
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-2">
          <Panel title={prototype ? "Agenten, Prototypdaten" : "Agenten"}>
            <DataTable
              rows={data.agents}
              columns={cols}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </Panel>
          {selected && (
            <DetailPanel title="Agentendetails">
              <DetailRow label="Name" value={selected.name} />
              <DetailRow label="Rolle" value={selected.role} />
              <DetailRow
                label="Zustand"
                value={<StatusBadge tone={selected.status} label="Nicht verbunden" />}
              />
              <DetailRow label="Modell" value={selected.model} />
              <DetailRow label="Aktivität" value={selected.lastActivity} />
              <p className="text-[11px] leading-5 text-muted-foreground">{selected.description}</p>
              <UnsupportedAction adapter={adapter} capability="agent.start">
                Starten
              </UnsupportedAction>
              <UnsupportedAction adapter={adapter} capability="agent.configure">
                Konfigurieren
              </UnsupportedAction>
            </DetailPanel>
          )}
        </div>
        <Panel title={prototype ? "Beispielaktivität" : "Aktivität"}>
          <ActivityFeed rows={data.activities.filter((a) => a.source === "Agenten")} limit={4} />
        </Panel>
      </div>
    </>
  );
}

export function VoiceSection({ data, adapter }: { data: JarvisSnapshot; adapter: JarvisAdapter }) {
  const prototype = usePrototype();
  const [gain, setGain] = useState([68]);
  const [vad, setVad] = useState(true);
  return (
    <>
      <SectionHeader
        title="Voice"
        description={
          prototype
            ? "Konfigurierte Spracharchitektur ohne Live-Verbindung"
            : "Keine Voice-Schnittstelle im Backend; Chatterbox-Health siehe System"
        }
      />
      <Tabs defaultValue="overview" className="p-3">
        <TabsList>
          <TabsTrigger value="overview">Übersicht</TabsTrigger>
          <TabsTrigger value="input">Eingabe</TabsTrigger>
          <TabsTrigger value="stt">Spracherkennung</TabsTrigger>
          <TabsTrigger value="tts">Sprachausgabe</TabsTrigger>
          <TabsTrigger value="settings">Einstellungen</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="mt-2 space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <Panel title="Mikrofon und Eingabe">
              <div className="space-y-3 p-3">
                <div className="flex items-center gap-2">
                  {prototype && <StatusDot tone="offline" />}
                  <strong className="text-sm">{prototype ? "Nicht verbunden" : unavailable}</strong>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {data.voice.device}
                  {data.voice.sampleRate !== null && ` · ${data.voice.sampleRate} Hz`}
                  {data.voice.channels !== null && ` · ${data.voice.channels} Kanal`}
                </p>
                <div className="flex h-8 items-center justify-center border border-border text-[10px] text-muted-foreground">
                  Kein Live-Audiosignal
                </div>
                <UnsupportedAction adapter={adapter} capability="voice.listen">
                  Aufnahme starten
                </UnsupportedAction>
              </div>
            </Panel>
            <Panel title="Spracherkennung">
              <KeyValueList
                rows={[
                  { label: "Backend", value: data.voice.sttBackend },
                  { label: "Modell", value: data.voice.sttModel },
                  { label: "Runtime", value: data.voice.sttRuntime },
                  { label: "Provider", value: data.voice.sttProvider },
                  { label: "Sprache", value: data.voice.language },
                  { label: "Threads", value: num(data.voice.sttThreads) },
                ]}
              />
            </Panel>
            <Panel title="Sprachausgabe">
              <KeyValueList
                rows={[
                  { label: "Primär", value: data.voice.tts },
                  { label: "Endpoint", value: data.voice.ttsEndpoint },
                  {
                    label: "Warmup",
                    value:
                      data.voice.ttsWarmup === null
                        ? unavailable
                        : data.voice.ttsWarmup
                          ? "Aktiviert"
                          : "Deaktiviert",
                  },
                  { label: "Fallback", value: data.voice.ttsFallback },
                  { label: "Alternative", value: data.voice.ttsAlternative },
                  {
                    label: "Health",
                    value: serviceOf(data, "Chatterbox")?.configuration ?? "Nicht verbunden",
                  },
                ]}
              />
            </Panel>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Panel title="Live-Transkription">
              <div className="flex h-40 items-center justify-center p-4 text-xs text-muted-foreground">
                Noch keine Runtime-Daten
              </div>
            </Panel>
            <Panel title={prototype ? "Pipeline-Beispiele" : "Pipeline-Ereignisse"}>
              <ActivityFeed rows={data.activities.filter((a) => a.source === "Voice")} limit={5} />
            </Panel>
          </div>
        </TabsContent>
        {["input", "stt", "tts", "settings"].map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-2">
            <Panel title={prototype ? "Lokale Prototyp-Einstellungen" : "Lokale Darstellung"}>
              <div className="max-w-xl space-y-5 p-4">
                <div>
                  <div className="mb-2 flex justify-between text-xs">
                    <span>Darstellung Eingangsverstärkung</span>
                    <span>{gain[0]} %</span>
                  </div>
                  <Slider value={gain} onValueChange={setGain} max={100} />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <div>Darstellung Sprachaktivität</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">
                      {prototype
                        ? "Nur lokal im Prototyp, ändert keine Backend-Konfiguration."
                        : "Nur lokale Darstellung, ändert keine Backend-Konfiguration."}
                    </div>
                  </div>
                  <Switch checked={vad} onCheckedChange={setVad} />
                </div>
              </div>
            </Panel>
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}

export function MemorySection({ data }: { data: JarvisSnapshot }) {
  const prototype = usePrototype();
  const [query, setQuery] = useState("");
  const [tier, setTier] = useState("all");
  const filtered = data.memories.filter(
    (m) =>
      (tier === "all" || m.tier === tier) &&
      `${m.subject} ${m.value}`.toLowerCase().includes(query.toLowerCase()),
  );
  const [selected, setSelected] = useState(data.memories[0]);
  const cols: Column<MemoryItem>[] = [
    {
      key: "subject",
      label: "Subjekt",
      render: (m) => <span className="font-medium">{m.subject}</span>,
    },
    { key: "value", label: "Wert", render: (m) => m.value },
    { key: "tier", label: "Ebene", render: (m) => m.tier },
    { key: "confidence", label: "Konfidenz", render: (m) => `${m.confidence} %` },
    { key: "last", label: "Zuletzt gesehen", render: (m) => m.lastSeen },
  ];
  return (
    <>
      <SectionHeader
        title="Memory"
        description={
          prototype
            ? "Architektur und klar markierte Prototyp-Fixtures"
            : "Zähler laut Backend; keine Eintragsliste (Backend kennt keine Working/Candidate/Confirmed-Ebenen)"
        }
      />
      <div className="space-y-2 p-3">
        <SummaryGrid
          metrics={[
            {
              label: "Live-Status",
              value:
                data.memoryCounts?.facts != null
                  ? "Zähler erreichbar"
                  : prototype
                    ? "Nicht verbunden"
                    : unavailable,
              ...(data.memoryCounts?.facts != null
                ? { tone: "online" as const }
                : prototype
                  ? { tone: "offline" as const }
                  : {}),
            },
            {
              label: "Faktenspeicher",
              value: "SQLite",
              ...(prototype ? {} : { detail: "laut Code" }),
              tone: "info",
            },
            {
              label: "Semantikindex",
              value: "FAISS",
              ...(prototype ? {} : { detail: "laut Code" }),
              tone: "info",
            },
            {
              label: "Live-Zähler",
              value:
                data.memoryCounts?.facts === undefined || data.memoryCounts.facts === null
                  ? unavailable
                  : `${data.memoryCounts.facts} Fakten`,
              ...(data.memoryCounts?.vectors !== undefined && data.memoryCounts.vectors !== null
                ? { detail: `${data.memoryCounts.vectors} FAISS-Vektoren` }
                : {}),
            },
          ]}
        />
        <Panel title="Memory-Funktionen">
          <KeyValueList
            rows={[
              ...data.memoryArchitecture.stores.map((x) => ({ label: x, value: "Implementiert" })),
              ...data.memoryArchitecture.features.map((x) => ({
                label: x.name,
                value: x.implemented ? "Implementiert" : "Nicht implementiert",
              })),
            ]}
          />
        </Panel>
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-2">
          <Panel title={prototype ? "Speichereinträge, Prototypdaten" : "Speichereinträge"}>
            <div className="flex gap-2 border-b border-border p-2">
              <div className="relative flex-1">
                <Search className="absolute left-2 top-2 size-3.5 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-8"
                  placeholder={
                    prototype ? "Beispieldaten durchsuchen..." : "Einträge durchsuchen..."
                  }
                />
              </div>
              <Select value={tier} onValueChange={setTier}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Ebenen</SelectItem>
                  <SelectItem value="Working">Working</SelectItem>
                  <SelectItem value="Candidate">Candidate</SelectItem>
                  <SelectItem value="Confirmed">Confirmed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <DataTable
              rows={filtered}
              columns={cols}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </Panel>
          {selected && (
            <DetailPanel title="Speicherdetails">
              <DetailRow label="Subjekt" value={selected.subject} />
              <DetailRow label="Wert" value={selected.value} />
              <DetailRow label="Ebene" value={selected.tier} />
              <DetailRow label="Konfidenz" value={`${selected.confidence} %`} />
              <DetailRow label="Evidenzen" value={selected.evidence} />
              <DetailRow label="Herkunft" value={selected.provenance} />
              <DetailRow label="Erstellt" value={selected.created} />
              <DetailRow label="Zuletzt" value={selected.lastSeen} />
              <DetailRow label="Ersetzt" value={selected.superseded ? "Ja" : "Nein"} />
            </DetailPanel>
          )}
        </div>
      </div>
    </>
  );
}

export function ToolsSection({ data, adapter }: { data: JarvisSnapshot; adapter: JarvisAdapter }) {
  const prototype = usePrototype();
  const offlineTone = prototype ? ({ tone: "offline" } as const) : {};
  const [selected, setSelected] = useState(data.tools[0]);
  const cols: Column<ToolItem>[] = [
    {
      key: "name",
      label: "Werkzeug",
      render: (t) => <span className="font-medium">{t.name}</span>,
    },
    { key: "type", label: "Typ", render: (t) => t.type },
    {
      key: "status",
      label: "Status",
      render: (t) => <StatusBadge tone={t.status} label="Nicht verbunden" />,
    },
    { key: "desc", label: "Beschreibung", render: (t) => t.description },
    { key: "scope", label: "Umfang", render: (t) => t.scope },
    { key: "last", label: "Letzte Nutzung", render: (t) => t.lastUse },
  ];
  return (
    <>
      <SectionHeader
        title="Tools"
        description={
          prototype
            ? "Prototyp-Fixtures ohne behauptete Laufzeitaktivität"
            : "Keine Werkzeug-Schnittstelle im Backend"
        }
      />
      <div className="space-y-2 p-3">
        <SummaryGrid
          metrics={[
            { label: prototype ? "Beispielzeilen" : "Einträge", value: String(data.tools.length) },
            { label: "Live verfügbar", value: unavailable, tone: "offline" },
            { label: "Berechtigungen", value: prototype ? "Nicht verbunden" : unavailable },
            { label: "Letzte Nutzung", value: unavailable },
          ]}
        />
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-2">
          <Panel title={prototype ? "Werkzeugverzeichnis, Prototypdaten" : "Werkzeugverzeichnis"}>
            <DataTable
              rows={data.tools}
              columns={cols}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </Panel>
          {selected && (
            <DetailPanel title="Werkzeugdetails">
              <DetailRow label="Werkzeug" value={selected.name} />
              <DetailRow label="Typ" value={selected.type} />
              <DetailRow
                label="Status"
                value={<StatusBadge tone={selected.status} label="Nicht verbunden" />}
              />
              <DetailRow label="Umfang" value={selected.scope} />
              <p className="text-[11px] leading-5 text-muted-foreground">{selected.description}</p>
              <UnsupportedAction adapter={adapter} capability="tool.configure">
                Konfigurieren
              </UnsupportedAction>
            </DetailPanel>
          )}
        </div>
        <Panel title={prototype ? "Prüfbeispiele" : "Prüfungen"}>
          <ActivityFeed rows={data.activities.filter((a) => a.source === "Tools")} limit={4} />
        </Panel>
      </div>
    </>
  );
}

export function AutomationsSection({
  data,
  adapter,
}: {
  data: JarvisSnapshot;
  adapter: JarvisAdapter;
}) {
  const prototype = usePrototype();
  const [selected, setSelected] = useState(data.automations[0]);
  const [open, setOpen] = useState(false);
  const cols: Column<Automation>[] = [
    { key: "name", label: "Name", render: (a) => <span className="font-medium">{a.name}</span> },
    { key: "trigger", label: "Auslöser", render: (a) => a.trigger },
    { key: "last", label: "Letzter Lauf", render: (a) => a.lastRun },
    {
      key: "status",
      label: "Status",
      render: (a) => <StatusBadge tone={a.status} label="Nicht verbunden" />,
    },
    { key: "actions", label: "Aktionen", render: () => <ChevronRight className="size-3" /> },
  ];
  return (
    <>
      <SectionHeader
        title="Automations"
        description={
          prototype
            ? "Nicht ausführende Prototypregeln und Editorstruktur"
            : "Keine Automations-Schnittstelle im Backend"
        }
        action={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus />
            Neue Automation
          </Button>
        }
      />
      <div className="space-y-2 p-3">
        <SummaryGrid
          metrics={[
            {
              label: prototype ? "Beispielregeln" : "Regeln",
              value: String(data.automations.length),
            },
            { label: "Aktiv", value: unavailable },
            { label: "Fehlgeschlagen", value: unavailable },
            { label: "Letzte Läufe", value: unavailable },
          ]}
        />
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-2">
          <Panel title={prototype ? "Automationen, Prototypdaten" : "Automationen"}>
            <DataTable
              rows={data.automations}
              columns={cols}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </Panel>
          {selected && (
            <DetailPanel title="Automationsdetails">
              <DetailRow label="Name" value={selected.name} />
              <DetailRow label="Auslöser" value={selected.trigger} />
              <DetailRow label="Letzter Lauf" value={selected.lastRun} />
              <DetailRow
                label="Status"
                value={<StatusBadge tone={selected.status} label="Nicht verbunden" />}
              />
              <DetailRow label="Läufe" value={selected.runs} />
              <p className="text-[11px] leading-5 text-muted-foreground">{selected.description}</p>
              <UnsupportedAction adapter={adapter} capability="automation.run">
                Jetzt ausführen
              </UnsupportedAction>
            </DetailPanel>
          )}
        </div>
        <Panel title="Ausführungsprotokoll">
          <div className="flex h-24 items-center justify-center text-[11px] text-muted-foreground">
            Keine Live-Daten
          </div>
        </Panel>
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="w-[420px] sm:max-w-[420px]">
          <SheetHeader>
            <SheetTitle>Neue Automation</SheetTitle>
            <SheetDescription>Editorstruktur für eine spätere Runtime-Verbindung.</SheetDescription>
          </SheetHeader>
          <div className="mt-6 space-y-4">
            <label className="block text-xs">
              Name
              <Input className="mt-1" placeholder="Automation benennen" />
            </label>
            <label className="block text-xs">
              Auslöser
              <Select>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Auslöser wählen" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="time">Zeitplan</SelectItem>
                  <SelectItem value="event">Systemereignis</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <NotImplementedState />
          </div>
          <SheetFooter className="mt-6">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Schließen
            </Button>
            <Button disabled>Speichern</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}

type ExecuteAction = (capability: Capability) => Promise<AdapterResult>;

function RuntimePanel({
  data,
  adapter,
  onExecute,
}: {
  data: JarvisSnapshot;
  adapter: JarvisAdapter;
  onExecute?: ExecuteAction | undefined;
}) {
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string>();
  const run = async (capability: Capability) => {
    if (!onExecute) return;
    setBusy(true);
    try {
      // Backend action, then the hook reloads; the shown state always comes from the backend.
      const result = await onExecute(capability);
      setFeedback(result.ok ? undefined : result.message);
    } finally {
      setBusy(false);
    }
  };
  const prototype = usePrototype();
  const status = data.runtime;
  const view = presentRuntimeState(status.state);
  // With a live supervisor a disabled button means "not allowed right now", not "not implemented".
  const supervised = !prototype && status.state !== "NOT_IMPLEMENTED";
  const disabledTitle = supervised ? "Vom Supervisor derzeit nicht erlaubt" : "Nicht implementiert";
  const reasons =
    status.degradedReasons && status.degradedReasons.length > 0
      ? status.degradedReasons
      : status.degradedReason
        ? [status.degradedReason]
        : [];
  const showReason = status.state === "DEGRADED" || reasons.length > 0;
  return (
    <Panel title="Runtime">
      <div className="flex flex-wrap items-center gap-4 px-3 py-2 text-[11px]">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Backend-Zustand</span>
          <StatusBadge tone={view.tone} label={view.label} />
        </div>
        {status.detail && <span className="text-muted-foreground">{status.detail}</span>}
        {showReason && (
          <span className="text-muted-foreground">
            Grund: {reasons.length > 0 ? reasons.join("; ") : "Kein Grund vom Backend gemeldet"}
          </span>
        )}
        {status.components?.map((component) => (
          <span key={component.id} className="flex items-center gap-1.5" title={component.detail}>
            <span className="text-muted-foreground">{component.name}</span>
            <StatusBadge
              tone={presentRuntimeState(component.state).tone}
              label={presentRuntimeState(component.state).label}
            />
          </span>
        ))}
        {status.backendTimestamp && (
          <span className="text-muted-foreground">
            Stand:{" "}
            {Number.isNaN(Date.parse(status.backendTimestamp))
              ? status.backendTimestamp
              : new Date(status.backendTimestamp).toLocaleString("de-DE")}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1">
          {(
            [
              ["runtime.start", "Start"],
              ["runtime.stop", "Stop"],
              ["runtime.restart", "Neustart"],
            ] as const
          ).map(([cap, label]) => (
            <Button
              key={cap}
              size="sm"
              variant="outline"
              disabled={busy || !onExecute || !adapter.hasCapability(cap)}
              title={adapter.hasCapability(cap) ? undefined : disabledTitle}
              onClick={() => void run(cap)}
            >
              {label}
            </Button>
          ))}
          {!["runtime.start", "runtime.stop", "runtime.restart"].some((c) =>
            adapter.hasCapability(c as "runtime.start"),
          ) &&
            (supervised ? (
              <span className="text-[10px] text-muted-foreground">
                Vom Supervisor nicht erlaubt
              </span>
            ) : (
              <NotImplementedState compact />
            ))}
        </div>
        {feedback && <span className="w-full text-status-warning">{feedback}</span>}
      </div>
    </Panel>
  );
}
export function SystemSection({
  data,
  adapter,
  onExecute,
}: {
  data: JarvisSnapshot;
  adapter: JarvisAdapter;
  onExecute?: ExecuteAction | undefined;
}) {
  const prototype = usePrototype();
  const platformRows = [
    { label: "Host", value: data.platform.host },
    { label: "Linux-Runtime", value: data.platform.linuxRuntime },
    { label: "Architektur", value: data.platform.architecture },
    { label: "Betriebszeit", value: unavailable },
    { label: "Runtime", value: presentRuntimeState(data.runtime.state).label },
  ];
  return (
    <>
      <SectionHeader
        title="System"
        description={
          prototype
            ? "Statische Plattformkonfiguration ohne Live-Telemetrie"
            : "Dienst-Erreichbarkeit; keine Host-Telemetrie im Backend"
        }
      />
      <Tabs defaultValue="übersicht" className="p-3">
        <TabsList>
          {["Übersicht", "Konfiguration", "Performance", "Hardware", "Netzwerk", "Diagnose"].map(
            (x) => (
              <TabsTrigger key={x} value={x.toLowerCase()}>
                {x}
              </TabsTrigger>
            ),
          )}
        </TabsList>
        <TabsContent value="übersicht" className="mt-2 space-y-2">
          <RuntimePanel data={data} adapter={adapter} onExecute={onExecute} />
          <SummaryGrid metrics={data.metrics} count={6} />
          <div className="grid grid-cols-2 gap-2">
            <Panel title="CPU und Arbeitsspeicher">
              <PerformanceChart data={data.performance} secondary />
            </Panel>
            <Panel title="GPU und VRAM">
              <PerformanceChart data={data.gpuPerformance} secondary />
            </Panel>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <Panel title="Dienste">
              <div className="divide-y divide-border">
                {data.services.map((s) => (
                  <div
                    key={s.name}
                    className="flex items-center justify-between px-3 py-2 text-[11px]"
                  >
                    <span className="flex items-center gap-2">
                      <StatusDot tone={s.health ?? "offline"} />
                      {s.name}
                    </span>
                    <span className="text-right text-muted-foreground">
                      {s.configuration}
                      <br />
                      {s.endpoint ?? "Health unbekannt"}
                    </span>
                  </div>
                ))}
              </div>
            </Panel>
            <Panel title="Systeminformationen">
              <KeyValueList rows={platformRows} />
            </Panel>
            <Panel title="Hardware">
              <KeyValueList
                rows={[
                  { label: "CPU", value: data.hardware.cpu },
                  { label: "GPU", value: data.hardware.gpu },
                  { label: "RAM", value: data.hardware.ramCapacity },
                  { label: "VRAM", value: data.hardware.vramCapacity },
                  { label: "Auslastung", value: unavailable },
                ]}
              />
            </Panel>
          </div>
          <Panel title="System- und Diagnoseereignisse">
            <ActivityFeed rows={data.activities.filter((a) => a.source === "System")} limit={5} />
          </Panel>
        </TabsContent>
        {["konfiguration", "performance", "hardware", "netzwerk", "diagnose"].map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-2">
            <div className="grid grid-cols-2 gap-2">
              <Panel title={tab}>
                <PerformanceChart
                  data={tab === "hardware" ? data.gpuPerformance : data.performance}
                  secondary
                />
              </Panel>
              <Panel title={prototype ? "Konfigurierte Dienste" : "Dienste"}>
                <KeyValueList
                  rows={data.services.slice(0, 6).map((s) => ({
                    label: s.name,
                    value:
                      s.health === undefined
                        ? `${s.configuration}, Health unbekannt`
                        : s.configuration,
                  }))}
                />
              </Panel>
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}

export function LogsSection({ data, adapter }: { data: JarvisSnapshot; adapter: JarvisAdapter }) {
  const prototype = usePrototype();
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("all");
  const [paused, setPaused] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const selected = data.activities.find((a) => a.id === selectedId) ?? data.activities[0];
  const filtered = useMemo(
    () =>
      data.activities.filter(
        (l) =>
          (level === "all" || l.level === level) &&
          `${l.source} ${l.message} ${l.context}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [data.activities, level, query],
  );
  const topSource = useMemo(() => {
    const counts = new Map<string, number>();
    data.activities.forEach((x) => counts.set(x.source, (counts.get(x.source) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "Keine Daten";
  }, [data.activities]);
  const cols: Column<LogItem>[] = [
    { key: "time", label: "Zeit", className: "w-24 font-mono", render: (l) => l.time },
    { key: "source", label: "Quelle", render: (l) => l.source },
    {
      key: "level",
      label: "Level",
      render: (l) => (
        <StatusBadge
          tone={l.level === "Fehler" ? "error" : l.level === "Warnung" ? "warning" : "info"}
          label={l.level}
        />
      ),
    },
    { key: "message", label: "Nachricht", render: (l) => l.message },
    {
      key: "context",
      label: "Kontext",
      render: (l) => <span className="font-mono text-[10px]">{l.context}</span>,
    },
  ];
  return (
    <>
      <SectionHeader
        title="Logs"
        description={
          prototype
            ? "Klar markierte Beispielereignisse, keine Live-Protokolle"
            : "Watchdog-Ereignisse der letzten 24 Stunden, keine vollständigen Logs"
        }
      />
      <div className="space-y-2 p-3">
        <Panel>
          <div className="flex items-center gap-2 p-2">
            <Select defaultValue="all">
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{prototype ? "Alle Beispiele" : "Alle Quellen"}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={level} onValueChange={setLevel}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle Level</SelectItem>
                <SelectItem value="Info">Info</SelectItem>
                <SelectItem value="Warnung">Warnung</SelectItem>
                <SelectItem value="Fehler">Fehler</SelectItem>
                <SelectItem value="Debug">Debug</SelectItem>
              </SelectContent>
            </Select>
            <div className="relative flex-1">
              <Search className="absolute left-2 top-2 size-3.5 text-muted-foreground" />
              <Input
                className="pl-8"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={
                  prototype ? "Beispielereignisse durchsuchen..." : "Ereignisse durchsuchen..."
                }
              />
            </div>
            <Button
              size="icon"
              variant={paused ? "secondary" : "outline"}
              onClick={() => setPaused(!paused)}
              disabled={!prototype}
              title={
                !prototype ? "Kein Live-Stream im Backend" : paused ? "Fortsetzen" : "Pausieren"
              }
            >
              {paused ? <Play /> : <Pause />}
            </Button>
            <Button
              size="icon"
              variant="outline"
              disabled={!adapter.hasCapability("logs.export")}
              title="Export nicht implementiert"
            >
              <Download />
            </Button>
          </div>
        </Panel>
        <div className="grid grid-cols-[minmax(0,1fr)_300px] gap-2">
          <Panel title={`${filtered.length} ${prototype ? "Beispiele" : "Ereignisse"}`}>
            <DataTable
              rows={filtered}
              columns={cols}
              selectedId={selected?.id}
              onSelect={(row) => setSelectedId(row.id)}
            />
          </Panel>
          <DetailPanel title={prototype ? "Auswertung, Prototyp" : "Auswertung"}>
            <DetailRow
              label="Fehler"
              value={data.activities.filter((x) => x.level === "Fehler").length}
            />
            <DetailRow
              label="Warnungen"
              value={data.activities.filter((x) => x.level === "Warnung").length}
            />
            <DetailRow
              label="Info"
              value={data.activities.filter((x) => x.level === "Info").length}
            />
            <DetailRow label="Top-Quelle" value={topSource} />
            {selected && (
              <>
                <div className="pt-2 text-[10px] font-semibold uppercase text-muted-foreground">
                  {prototype ? "Ausgewähltes Beispiel" : "Ausgewähltes Ereignis"}
                </div>
                <DetailRow label="Zeit" value={selected.time} />
                <DetailRow label="Quelle" value={selected.source} />
                <DetailRow label="Nachricht" value={selected.message} />
                <DetailRow
                  label="Kontext"
                  value={<span className="font-mono">{selected.context}</span>}
                />
              </>
            )}
          </DetailPanel>
        </div>
      </div>
    </>
  );
}

function SettingRow({
  title,
  text,
  control,
}: {
  title: string;
  text: string;
  control: React.ReactNode;
}) {
  return (
    <div className="grid min-h-14 grid-cols-[1fr_220px] items-center gap-4 border-b border-border px-3 py-2">
      <div>
        <div className="text-xs">{title}</div>
        <div className="mt-1 text-[10px] text-muted-foreground">{text}</div>
      </div>
      <div className="flex justify-end">{control}</div>
    </div>
  );
}
export function SettingsSection({ data }: { data: JarvisSnapshot }) {
  const prototype = usePrototype();
  const get = (k: string, d: boolean) =>
    typeof window !== "undefined" && localStorage.getItem(k) !== null
      ? localStorage.getItem(k) === "true"
      : d;
  const [confirm, setConfirm] = useState(() => get("jarvis-confirm", true));
  const [active, setActive] = useState("Allgemein");
  const persist = (key: string, setter: (v: boolean) => void) => (v: boolean) => {
    setter(v);
    localStorage.setItem(key, String(v));
  };
  const sections = [
    "Allgemein",
    "Oberfläche",
    "Modelle",
    "Datenschutz / Lokalität",
    "Stimme",
    "Integrationen",
    "Updates",
    "Daten & Speicher",
    "Hilfe & Informationen",
  ];
  const content: Record<string, React.ReactNode> = {
    Allgemein: (
      <Panel title="Allgemein">
        <SettingRow
          title="Sprache"
          text="Sprache der Desktop-Oberfläche"
          control={<span className="text-xs">Deutsch</span>}
        />
        <SettingRow
          title="Bestätigung vor Aktionen"
          text="Lokale Oberflächenpräferenz"
          control={
            <Switch checked={confirm} onCheckedChange={persist("jarvis-confirm", setConfirm)} />
          }
        />
      </Panel>
    ),
    Oberfläche: (
      <Panel title="Oberfläche">
        <SettingRow
          title="Design"
          text="Festes Graphit-Design der Desktop-Oberfläche"
          control={<span className="text-xs">Graphit</span>}
        />
        <SettingRow
          title="Dichte"
          text="Kompakte Informationsdarstellung"
          control={<span className="text-xs">Kompakt</span>}
        />
      </Panel>
    ),
    Modelle: (
      <Panel title="Modelle">
        <SettingRow
          title="Main LLM"
          text={prototype ? data.model.endpoint : "Dienst-Erreichbarkeit"}
          control={
            prototype ? (
              <span className="text-xs">Konfiguriert</span>
            ) : (
              <StatusBadge
                tone={serviceOf(data, "Main LLM")?.health ?? "offline"}
                label={serviceOf(data, "Main LLM")?.configuration ?? "Nicht verbunden"}
              />
            )
          }
        />
        <SettingRow
          title="Runtime-Steuerung"
          text="Änderungen benötigen eine Runtime-Verbindung"
          control={
            <Button size="sm" disabled>
              {prototype ? "Nicht verbunden" : "Nicht implementiert"}
            </Button>
          }
        />
      </Panel>
    ),
    "Datenschutz / Lokalität": (
      <Panel title="Datenschutz und Lokalität">
        <SettingRow
          title="PrivacyGate"
          text="Im Backend implementiert, Desktop-Steuerung noch nicht verbunden"
          control={
            <StatusBadge
              tone="info"
              label={prototype ? "Implementiert" : "Implementiert (laut Code)"}
            />
          }
        />
        <SettingRow
          title="Aktueller Modus"
          text={
            prototype
              ? "Ohne Runtime-Verbindung nicht feststellbar"
              : "Keine Schnittstelle im Backend"
          }
          control={
            <StatusBadge
              tone={prototype ? "offline" : "idle"}
              label={prototype ? "Nicht verbunden" : unavailable}
            />
          }
        />
        <SettingRow
          title="Netzwerkzustand"
          text={
            prototype
              ? "Ohne Runtime-Verbindung nicht feststellbar"
              : "Keine Schnittstelle im Backend"
          }
          control={
            <StatusBadge
              tone={prototype ? "offline" : "idle"}
              label={prototype ? "Nicht verbunden" : unavailable}
            />
          }
        />
      </Panel>
    ),
    Stimme: (
      <Panel title="Stimme">
        <SettingRow
          title="Wake Word"
          text={
            prototype
              ? `${data.voice.wakeEngine}, Keyword ${data.voice.wakeKeyword}`
              : "Keine Schnittstelle im Backend"
          }
          control={<span className="text-xs">{prototype ? "Konfiguriert" : unavailable}</span>}
        />
        <SettingRow
          title="Spracherkennung"
          text={
            prototype
              ? `${data.voice.sttBackend} über ${data.voice.sttRuntime}`
              : "Keine Schnittstelle im Backend"
          }
          control={<span className="text-xs">{prototype ? "Konfiguriert" : unavailable}</span>}
        />
        <SettingRow
          title="Sprachausgabe"
          text={
            prototype
              ? `${data.voice.tts}, Fallback ${data.voice.ttsFallback}`
              : "Nur Health-Abfrage vorhanden, siehe System"
          }
          control={<span className="text-xs">{prototype ? "Konfiguriert" : unavailable}</span>}
        />
      </Panel>
    ),
    Integrationen: (
      <Panel title="Integrationen">
        <SettingRow
          title="Small LLM"
          text={prototype ? "Konfiguriert, aktueller Health unbekannt" : "Dienst-Erreichbarkeit"}
          control={
            <StatusBadge
              tone={serviceOf(data, "Small LLM")?.health ?? "offline"}
              label={serviceOf(data, "Small LLM")?.configuration ?? "Nicht verbunden"}
            />
          }
        />
        <SettingRow
          title="FLUX.2 Klein 4B"
          text={prototype ? "Lokaler Server auf Port 8190 konfiguriert" : "Dienst-Erreichbarkeit"}
          control={
            <StatusBadge
              tone={serviceOf(data, "FLUX.2 Klein 4B")?.health ?? "offline"}
              label={serviceOf(data, "FLUX.2 Klein 4B")?.configuration ?? "Nicht verbunden"}
            />
          }
        />
      </Panel>
    ),
    Updates: (
      <Panel title="Updates">
        <SettingRow
          title="Update-Status"
          text="Keine verbundene Updatequelle"
          control={<StatusBadge tone="offline" label="Nicht verbunden" />}
        />
        <SettingRow
          title="Runtime-Version"
          text="Keine Runtime-Daten"
          control={<span className="text-xs">{prototype ? "Unbekannt" : unavailable}</span>}
        />
      </Panel>
    ),
    "Daten & Speicher": (
      <Panel title="Daten und Speicher">
        <SettingRow
          title="Metrics-Datenbank"
          text={
            data.metricsRetentionDays === null
              ? "Konfigurierte Aufbewahrung: Keine Live-Daten"
              : `Konfigurierte Aufbewahrung: ${data.metricsRetentionDays} Tage`
          }
          control={
            <span className="text-xs">
              {prototype ? "Implementiert" : "Implementiert (laut Code)"}
            </span>
          }
        />
        <SettingRow
          title="Memory"
          text={prototype ? data.memoryArchitecture.stores.join(", ") : "Zähler siehe Memory"}
          control={<span className="text-xs">{prototype ? "Konfiguriert" : unavailable}</span>}
        />
      </Panel>
    ),
    "Hilfe & Informationen": (
      <Panel title="Hilfe und Informationen">
        <SettingRow
          title="JARVIS Control Hub"
          text={
            prototype
              ? "Desktop-Prototyp ohne Live-Verbindung"
              : "Desktop-UI mit Produktionsadapter"
          }
          control={prototype ? <PrototypeIndicator /> : <span className="text-xs">Produktion</span>}
        />
        <SettingRow
          title="Backend"
          text={prototype ? "JARVIS Sleepy Konfiguration" : "Keine Konfigurations-Schnittstelle"}
          control={
            <span className="text-xs">{prototype ? "Quelle der Konfiguration" : unavailable}</span>
          }
        />
      </Panel>
    ),
  };
  return (
    <>
      <SectionHeader
        title="Einstellungen"
        description="Lokale Einstellungen und adapterbasierte Konfiguration"
      />
      <div className="grid grid-cols-[190px_minmax(0,780px)] gap-3 p-3">
        <nav className="border border-border bg-card p-1" aria-label="Einstellungskategorien">
          {sections.map((s) => (
            <button
              key={s}
              onClick={() => setActive(s)}
              className={cn(
                "flex h-8 w-full items-center px-2 text-left text-[11px] transition-colors hover:bg-accent",
                active === s && "bg-selection text-primary",
              )}
            >
              {s}
            </button>
          ))}
        </nav>
        <div className="space-y-2">{content[active]}</div>
      </div>
    </>
  );
}
