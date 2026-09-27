import type { ReactNode } from "react";
import { AlertCircle, Box, CloudOff, LoaderCircle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Metric, StatusTone } from "@/lib/jarvis/types";

const toneClass: Record<StatusTone, string> = {
  online: "bg-status-online",
  idle: "bg-status-idle",
  warning: "bg-status-warning",
  error: "bg-status-error",
  offline: "bg-status-offline",
  info: "bg-status-info",
};
const labels: Record<StatusTone, string> = {
  online: "Aktiv",
  idle: "Bereit",
  warning: "Warnung",
  error: "Fehler",
  offline: "Offline",
  info: "Info",
};

export function StatusDot({ tone, pulse = false }: { tone: StatusTone; pulse?: boolean }) {
  return (
    <span
      className={cn(
        "inline-block size-1.5 shrink-0 rounded-full",
        toneClass[tone],
        pulse && "animate-status-pulse",
      )}
    />
  );
}
export function StatusBadge({ tone, label }: { tone: StatusTone; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
      <StatusDot tone={tone} />
      {label ?? labels[tone]}
    </span>
  );
}
export function PrototypeIndicator() {
  return (
    <span className="rounded-sm border border-primary/40 bg-primary/10 px-1.5 py-0.5 text-[9px] font-bold tracking-[0.12em] text-primary">
      PROTOTYP
    </span>
  );
}
export function Brand() {
  return (
    <div>
      <div className="font-semibold tracking-[0.16em] text-foreground">J.A.R.V.I.S</div>
      <div className="mt-0.5 text-[10px] text-muted-foreground">Local AI Assistant</div>
      <div className="mt-1 text-[8px] font-medium uppercase tracking-[0.08em] text-primary">
        Unscheinbar. Überlegen. Meins.
      </div>
    </div>
  );
}
export function Panel({
  title,
  action,
  children,
  className,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("min-w-0 border border-border bg-card", className)}>
      {title && (
        <header className="flex h-9 items-center justify-between border-b border-border px-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {title}
          </h2>
          {action}
        </header>
      )}
      <div className="min-w-0">{children}</div>
    </section>
  );
}
export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between border-b border-border px-4">
      <div>
        <h1 className="text-base font-semibold text-foreground">{title}</h1>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  );
}
export function MetricCard({ metric }: { metric: Metric }) {
  return (
    <div className="min-w-0 border border-border bg-card p-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          {metric.label}
        </span>
        {metric.tone && <StatusDot tone={metric.tone} />}
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <strong className="text-xl font-semibold text-foreground">{metric.value}</strong>
        {metric.trend && <span className="text-[10px] text-muted-foreground">{metric.trend}</span>}
      </div>
      {metric.detail && (
        <p className="mt-1 truncate text-[10px] text-muted-foreground">{metric.detail}</p>
      )}
      {metric.progress !== undefined && (
        <div className="mt-2 h-1 overflow-hidden rounded-sm bg-muted">
          <div
            className="h-full bg-primary transition-[width]"
            style={{ width: `${Math.min(metric.progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
export function DetailPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Panel title={title} className="h-full">
      <div className="space-y-3 p-3">{children}</div>
    </Panel>
  );
}
export function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[104px_1fr] gap-2 border-b border-border/70 pb-2 text-[11px]">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words text-foreground">{value}</span>
    </div>
  );
}
function State({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center border border-border bg-card p-8 text-center">
      <div className="text-muted-foreground">{icon}</div>
      <h2 className="mt-3 text-sm font-semibold">{title}</h2>
      <p className="mt-1 max-w-sm text-xs text-muted-foreground">{text}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
export function LoadingState() {
  return (
    <State
      icon={<LoaderCircle className="size-5 animate-spin" />}
      title="Daten werden geladen"
      text="Verbindung zur JARVIS-Laufzeit wird vorbereitet."
    />
  );
}
export function EmptyState() {
  return (
    <State
      icon={<Box className="size-5" />}
      title="Keine Daten"
      text="Die Laufzeit hat für diesen Bereich keine Einträge geliefert."
    />
  );
}
export function ErrorState({ retry }: { retry?: () => void }) {
  return (
    <State
      icon={<AlertCircle className="size-5" />}
      title="Datenfehler"
      text="Die Laufzeitdaten konnten nicht gelesen werden."
      action={
        retry && (
          <Button size="sm" onClick={retry}>
            Erneut versuchen
          </Button>
        )
      }
    />
  );
}
export function OfflineState() {
  return (
    <State
      icon={<CloudOff className="size-5" />}
      title="Runtime offline"
      text="JARVIS ist derzeit nicht erreichbar. Es werden keine Betriebswerte angenommen."
    />
  );
}
export function NotImplementedState({ compact = false }: { compact?: boolean }) {
  return compact ? (
    <span className="text-[10px] text-status-warning">Nicht implementiert</span>
  ) : (
    <State
      icon={<ShieldAlert className="size-5" />}
      title="Nicht implementiert"
      text="Diese Aktion wird erst mit einer unterstützten Runtime-Verbindung verfügbar."
    />
  );
}
