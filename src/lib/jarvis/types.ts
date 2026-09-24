export type RuntimePhase =
  "loading" | "ready" | "empty" | "offline" | "error" | "not-implemented" | "prototype";
export type StatusTone = "online" | "idle" | "warning" | "error" | "offline" | "info";
export type SectionId =
  | "dashboard"
  | "ai-core"
  | "agents"
  | "voice"
  | "memory"
  | "tools"
  | "automations"
  | "system"
  | "logs"
  | "settings";

export interface RuntimeEnvelope<T> {
  phase: RuntimePhase;
  data?: T;
  message?: string;
  updatedAt: string;
}
export interface Metric {
  label: string;
  value: string;
  detail?: string;
  trend?: string;
  tone?: StatusTone;
  progress?: number;
}
export interface ChartPoint {
  time: string;
  primary: number;
  secondary?: number;
}
export interface Activity {
  id: string;
  time: string;
  source: string;
  level: "Info" | "Warnung" | "Fehler" | "Debug";
  message: string;
  context: string;
}
export interface Agent {
  id: string;
  name: string;
  role: string;
  status: StatusTone;
  model: string;
  lastActivity: string;
  tasks: number;
  description: string;
}
export interface MemoryItem {
  id: string;
  subject: string;
  value: string;
  tier: "Working" | "Candidate" | "Confirmed";
  confidence: number;
  evidence: number;
  provenance: string;
  created: string;
  lastSeen: string;
  superseded: boolean;
}
export interface ToolItem {
  id: string;
  name: string;
  type: string;
  status: StatusTone;
  description: string;
  scope: string;
  lastUse: string;
}
export interface Automation {
  id: string;
  name: string;
  trigger: string;
  lastRun: string;
  status: StatusTone;
  runs: number;
  description: string;
}
export interface ModelInfo {
  name: string;
  family: string;
  quantization: string;
  context: string;
  parameters: string;
  location: string;
  runtime: string;
  endpoint: string;
  gpuLayers: number | null;
  batchSize: number | null;
  ubatchSize: number | null;
  temperature: number | null;
  topP: number | null;
  topK: number | null;
  toolCalling: boolean | null;
  status: StatusTone;
}
export interface VoiceState {
  state?: "Idle" | "Listening" | "Processing" | "Speaking";
  input: string;
  device: string;
  sampleRate: number | null;
  channels: number | null;
  outputBackend: string;
  tempPath: string;
  language: string;
  wakeEngine: string;
  wakeKeyword: string;
  sttBackend: string;
  sttModel: string;
  sttRuntime: string;
  sttProvider: string;
  sttThreads: number | null;
  tts: string;
  ttsEndpoint: string;
  ttsConnectTimeout: string;
  ttsReadTimeout: string;
  ttsWarmup: boolean | null;
  ttsFallback: string;
  ttsAlternative: string;
  transcription?: string;
}
export interface ConfiguredService {
  name: string;
  endpoint?: string;
  configuration: string;
  health?: StatusTone;
}
export interface PlatformInfo {
  host: string;
  linuxRuntime: string;
  architecture: string;
}
export interface HardwareInfo {
  cpu: string;
  gpu: string;
  vramCapacity: string;
  ramCapacity: string;
}
export interface MemoryArchitecture {
  stores: string[];
  features: { name: string; implemented: boolean }[];
}
export interface PrivacyArchitecture {
  gateImplemented: boolean;
  modesImplemented: boolean;
  desktopConnected: boolean;
}
export type BackendRuntimeState =
  "STARTING" | "READY" | "DEGRADED" | "ERROR" | "STOPPED" | "OFFLINE" | "NOT_IMPLEMENTED";
export interface RuntimeComponent {
  id: string;
  name: string;
  state: BackendRuntimeState;
  detail?: string;
}
export interface RuntimeStatus {
  state: BackendRuntimeState;
  degradedReason?: string;
  /** Reasons reported by the runtime supervisor (see runtime-control.ts). */
  degradedReasons?: string[];
  /** Components as reported by the runtime supervisor. */
  components?: RuntimeComponent[];
  detail?: string;
  backendTimestamp?: string;
}
export interface JarvisSnapshot {
  runtime: RuntimeStatus;
  version: string;
  build: string;
  metrics: Metric[];
  performance: ChartPoint[];
  gpuPerformance: ChartPoint[];
  model: ModelInfo;
  activities: Activity[];
  agents: Agent[];
  memories: MemoryItem[];
  tools: ToolItem[];
  automations: Automation[];
  voice: VoiceState;
  platform: PlatformInfo;
  hardware: HardwareInfo;
  services: ConfiguredService[];
  memoryArchitecture: MemoryArchitecture;
  /** Live counts from the backend; absent when no verified source answered. */
  memoryCounts?: { facts: number | null; vectors: number | null };
  /** LLM interaction aggregates of the backend metrics DB; absent when no verified source answered. */
  llmStats?: { interactions: number; avgLatencyMs: number | null; hours: number };
  privacy: PrivacyArchitecture;
  metricsRetentionDays: number | null;
  subsystems: { name: string; status: StatusTone; detail: string }[];
  devices: { name: string; detail: string; status: StatusTone }[];
}
export type Capability =
  | "agent.start"
  | "agent.stop"
  | "agent.configure"
  | "tool.configure"
  | "automation.create"
  | "automation.run"
  | "logs.export"
  | "voice.listen"
  | "llm.prompt"
  | "privacy.control"
  | "runtime.start"
  | "runtime.stop"
  | "runtime.restart";
export interface AdapterResult {
  ok: boolean;
  phase: RuntimePhase;
  message: string;
}
export interface JarvisAdapter {
  readonly mode: "prototype" | "production";
  getSnapshot(): Promise<RuntimeEnvelope<JarvisSnapshot>>;
  hasCapability(capability: Capability): boolean;
  execute(capability: Capability, targetId?: string): Promise<AdapterResult>;
}
