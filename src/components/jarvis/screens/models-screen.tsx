import { useState } from "react";
import { HardDrive } from "lucide-react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { BottomSheet, Button, EmptyState, InlineNotice } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Modelle: local model and runtime management (Phase 5, System detail 1).
 *
 * Content follows the capability audit: LiteRT-LM provider, model manager and
 * downloader, background download with pause and resume, integrity check and
 * compatibility check all exist in the foundation. None of them is bound here,
 * so the screen reports capability, never activity. No model names, no sizes,
 * no accelerator, no throughput, no progress.
 *
 * Compose mapping: ModelsScreen(state: ModelsUiState, onBack), ModelListItem,
 * AddModelSheet.
 */

/* --------------------------- Model state model --------------------------- */

/**
 * Reusable load and download states for future real entries. Exactly one of
 * them describes a model at a time; the current baseline is "not_loaded".
 */
export type ModelLoadState =
  | "not_loaded"
  | "ready"
  | "downloading"
  | "paused"
  | "loading"
  | "incompatible"
  | "error";

export const modelLoadStateLabel: Record<ModelLoadState, string> = {
  not_loaded: "Nicht geladen",
  ready: "Bereit",
  downloading: "Wird heruntergeladen",
  paused: "Pausiert",
  loading: "Wird geladen",
  incompatible: "Inkompatibel",
  error: "Fehler",
};

/** Tone mapping onto the locked status language. */
export const modelLoadStateTone: Record<ModelLoadState, SystemState> = {
  not_loaded: "design_state",
  ready: "ready",
  downloading: "local",
  paused: "offline",
  loading: "local",
  incompatible: "degraded",
  error: "error",
};

export interface LocalModelEntry {
  id: string;
  name: string;
  /** Load or download state. Never inferred, always reported. */
  loadState: ModelLoadState;
  /** Result of the LiteRT compatibility check, once it has actually run. */
  compatible?: boolean;
  /** Local file size, only when it is really known. */
  size?: string;
  /** Short technical note, for example the file source. */
  note?: string;
}

/** Compact list entry for a local model file. Deliberately not a store card. */
export function ModelListItem({ model }: { model: LocalModelEntry }) {
  const compatibility =
    model.compatible === undefined
      ? "Kompatibilität nicht geprüft"
      : model.compatible
        ? "LiteRT-kompatibel"
        : "Nicht LiteRT-kompatibel";
  const subtitle = [compatibility, model.size, model.note].filter(Boolean).join(", ");
  return (
    <ListRow
      title={model.name}
      subtitle={subtitle}
      leading={<HardDrive className="size-4" aria-hidden />}
      trailing={
        <StatusTag
          state={modelLoadStateTone[model.loadState]}
          label={modelLoadStateLabel[model.loadState]}
          dot={false}
        />
      }
    />
  );
}

/* -------------------------- Management capabilities ---------------------- */

const managementCapabilities = [
  {
    title: "Import lokaler Modelle",
    detail: "Unterstützte Modelldateien aus dem Gerätespeicher übernehmen.",
  },
  {
    title: "Download im Hintergrund",
    detail: "Hintergrunddownload über WorkManager mit Netzwerkprüfung.",
  },
  {
    title: "Pause / Fortsetzen",
    detail: "Laufende Downloads anhalten und später fortsetzen.",
  },
  {
    title: "Integritätsprüfung",
    detail: "Prüfsumme nach SHA-256 nach dem Download.",
  },
  {
    title: "Kompatibilitätsprüfung",
    detail: "Prüfung gegen die LiteRT-Runtime vor dem Laden.",
  },
];

/* -------------------------------- Screen --------------------------------- */

export interface ModelsScreenProps {
  onBack: () => void;
}

/** Sources offered by the add-model sheet. */
type AddModelSource = "import" | "catalog";

export function ModelsScreen({ onBack }: ModelsScreenProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [source, setSource] = useState<AddModelSource | null>(null);
  /**
   * Prototype list. It stays empty because the registry is not bound yet; this
   * is not a claim that the real device carries no model file.
   */
  const localModels: LocalModelEntry[] = [];

  const closeSheet = () => {
    setSheetOpen(false);
    setSource(null);
  };

  return (
    <>
      <ScrollBody>
        <SectionEnter index={0}>
          <ModelsHeader onBack={onBack} />
        </SectionEnter>

        <SectionEnter index={1}>
          <SectionHeader>Aktueller Zustand</SectionHeader>
          <ListGroup>
            <ListRow
              title="Geladenes Modell"
              trailing={
                <StatusTag
                  state={modelLoadStateTone.not_loaded}
                  label={comparisonBaseline.labels.localModel}
                />
              }
            />
            <ListRow
              title="Lokale Runtime"
              subtitle="Vorgesehene Inferenz-Runtime auf dem Gerät."
              trailing={
                <span className="value-mono">{comparisonBaseline.labels.modelRuntime}</span>
              }
            />
            <ListRow
              title="Runtime-Bindung"
              trailing={
                <StatusTag state="design_state" label={comparisonBaseline.labels.runtime} />
              }
            />
          </ListGroup>
        </SectionEnter>

        <SectionEnter index={2}>
          <SectionHeader>Lokale Modelle</SectionHeader>
          {localModels.length === 0 ? (
            <div className="px-4">
              <EmptyState
                title="Keine Modelldaten verfügbar"
                body="Die lokale Modellregistrierung ist im Prototyp noch nicht an eine Runtime gebunden. Modelle können später lokal importiert oder über den Modellkatalog verwaltet werden."
              />
            </div>
          ) : (
            <ListGroup>
              {localModels.map((m) => (
                <ModelListItem key={m.id} model={m} />
              ))}
            </ListGroup>
          )}
          <div className="px-4 pt-3">
            <Button variant="primary" full onClick={() => setSheetOpen(true)}>
              Modell hinzufügen
            </Button>
          </div>
        </SectionEnter>

        <SectionEnter index={3}>
          <SectionHeader>Verwaltung</SectionHeader>
          <ListGroup>
            {managementCapabilities.map((c) => (
              <ListRow key={c.title} title={c.title} subtitle={c.detail} />
            ))}
          </ListGroup>
          <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
            Fähigkeiten der Modellverwaltung. Es werden hier keine laufenden
            Runtime-Vorgänge simuliert.
          </p>
        </SectionEnter>

        <SectionEnter index={4}>
          <p className="px-4 pt-5 pb-1 text-[11px] leading-4 text-muted-foreground">
            Entwurfszustand. Angezeigte Zustände stammen aus der aktuellen Projektbasis,
            nicht aus gemessener Laufzeittelemetrie.
          </p>
        </SectionEnter>
      </ScrollBody>

      <AddModelSheet
        open={sheetOpen}
        source={source}
        onSelect={setSource}
        onBackToChoice={() => setSource(null)}
        onClose={closeSheet}
      />
    </>
  );
}

/** Compact detail header with a native-feeling back affordance. */
function ModelsHeader({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex items-center gap-2 border-b border-border-soft bg-surface px-2 py-3">
      <button
        type="button"
        onClick={onBack}
        aria-label="Zurück zum Kontrollzentrum"
        className="j-pressable flex size-12 shrink-0 items-center justify-center rounded-sm"
      >
        <ArrowLeft className="size-5 text-subtle-foreground" aria-hidden />
      </button>
      <span className="min-w-0">
        <h1 className="text-[15px] leading-5 text-foreground">Modelle</h1>
        <p className="mt-0.5 text-[12px] leading-4 text-muted-foreground">Lokale Inferenz</p>
      </span>
    </div>
  );
}

/* ------------------------------ Add model -------------------------------- */

const sourceCopy: Record<AddModelSource, { title: string; body: string }> = {
  import: {
    title: "Lokale Datei importieren",
    body: "Die Dateiauswahl ist im Entwurfszustand noch nicht angebunden. Auswahl, Kompatibilitätsprüfung und Registrierung erfolgen später über die Android-Dateiauswahl.",
  },
  catalog: {
    title: "Modellkatalog öffnen",
    body: "Der Modellkatalog ist im Entwurfszustand noch nicht angebunden. Auswahl, Hintergrunddownload und Integritätsprüfung werden hier später über die Modellverwaltung ausgeführt.",
  },
};

function AddModelSheet({
  open,
  source,
  onSelect,
  onBackToChoice,
  onClose,
}: {
  open: boolean;
  source: AddModelSource | null;
  onSelect: (next: AddModelSource) => void;
  onBackToChoice: () => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={source ? sourceCopy[source].title : "Modell hinzufügen"}
    >
      {source ? (
        <div className="flex flex-col gap-3 px-4 pt-3">
          <InlineNotice tone="info">{sourceCopy[source].body}</InlineNotice>
          <div className="flex gap-2">
            <Button onClick={onBackToChoice}>Zurück</Button>
            <Button onClick={onClose}>Schließen</Button>
          </div>
        </div>
      ) : (
        <ListGroup>
          <ListRow
            title="Lokale Datei importieren"
            subtitle="Unterstützte lokale Modelldatei auswählen."
            chevron
            onClick={() => onSelect("import")}
          />
          <ListRow
            title="Modellkatalog öffnen"
            subtitle="Kompatibles Modell auswählen und lokal herunterladen."
            chevron
            onClick={() => onSelect("catalog")}
          />
        </ListGroup>
      )}
    </BottomSheet>
  );
}
