import { ArrowLeft } from "lucide-react";

/**
 * Shared compact header for detail screens under System and under Mehr.
 * Back affordance, title and one technical secondary line. No hero treatment.
 *
 * Compose mapping: JarvisDetailTopBar(title, subtitle, onBack).
 */
export function DetailHeader({
  title,
  subtitle,
  onBack,
  backLabel = "Zurück zum Kontrollzentrum",
}: {
  title: string;
  subtitle: string;
  onBack: () => void;
  backLabel?: string;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border-soft bg-surface px-2 py-3">
      <button
        type="button"
        onClick={onBack}
        aria-label={backLabel}
        className="j-pressable flex size-12 shrink-0 items-center justify-center rounded-sm"
      >
        <ArrowLeft className="size-5 text-subtle-foreground" aria-hidden />
      </button>
      <span className="min-w-0">
        <h1 className="text-[15px] leading-5 text-foreground">{title}</h1>
        <p className="mt-0.5 text-[12px] leading-4 text-muted-foreground">{subtitle}</p>
      </span>
    </div>
  );
}

/** Every detail screen, under System and under Mehr, takes the same contract. */
export interface DetailScreenProps {
  onBack: () => void;
}

/** Kept name for the System detail screens, same contract. */
export type SystemDetailProps = DetailScreenProps;

/** Back label for detail screens that live under the Mehr tab. */
export const MORE_BACK_LABEL = "Zurück zu Mehr";

/** Shared closing note: states come from the project base, not from telemetry. */
export function DesignStateNote() {
  return (
    <p className="px-4 pt-5 pb-1 text-[11px] leading-4 text-muted-foreground">
      Entwurfszustand. Angezeigte Zustände stammen aus der aktuellen Projektbasis, nicht
      aus gemessener Laufzeittelemetrie.
    </p>
  );
}
