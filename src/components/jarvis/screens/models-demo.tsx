import { useEffect, useRef, useState } from "react";
import { HardDrive } from "lucide-react";
import {
  ListGroup,
  ListRow,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import {
  BottomSheet,
  Button,
  Dialog,
  InlineNotice,
} from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import { DetailField, DEMO_AREA_NOTE, DESIGN_STATE_ACTION } from "@/components/jarvis/prototype-state";
import {
  modelLoadStateLabel,
  modelLoadStateTone,
  type LocalModelEntry,
  type ModelLoadState,
} from "@/components/jarvis/screens/models-screen";

/**
 * Zustandsdemonstration für die Modellverwaltung.
 *
 * Dieser Bereich ist ausdrücklich vom truthful baseline getrennt: er zeigt
 * Beispieleinträge mit einer lokalen Zustandsmaschine (Laden, Entladen,
 * Download starten/pausieren/fortsetzen/abbrechen, Löschen). Es handelt sich
 * um reinen React-Zustand im Speicher, keine Runtime- oder Gerätedaten.
 */

interface DemoModelEntry extends LocalModelEntry {
  source: "import" | "katalog";
  integrity?: "bestanden" | "fehlgeschlagen" | undefined;
  downloadProgress?: number | undefined;
  errorKind?: "laden" | "download" | undefined;
}

const initialDemoModels: DemoModelEntry[] = [
  {
    id: "demo-ready",
    name: "Beispielmodell A (bereit)",
    loadState: "ready",
    compatible: true,
    integrity: "bestanden",
    size: "412 MB",
    note: "Beispieleintrag",
    source: "import",
  },
  {
    id: "demo-downloading",
    name: "Beispielmodell B (Download läuft)",
    loadState: "downloading",
    compatible: true,
    size: "1,1 GB",
    note: "Beispieleintrag",
    source: "katalog",
    downloadProgress: 35,
  },
  {
    id: "demo-error",
    name: "Beispielmodell C (Fehler)",
    loadState: "error",
    compatible: true,
    integrity: "bestanden",
    size: "780 MB",
    note: "Beispieleintrag",
    source: "katalog",
    errorKind: "laden",
  },
  {
    id: "demo-incompatible",
    name: "Beispielmodell D (inkompatibel)",
    loadState: "incompatible",
    compatible: false,
    size: "2,3 GB",
    note: "Beispieleintrag",
    source: "katalog",
  },
];

function compatibilityLabel(compatible?: boolean) {
  if (compatible === undefined) return "Nicht geprüft";
  return compatible ? "Kompatibilitätsprüfung bestanden" : "Kompatibilitätsprüfung nicht bestanden";
}

function integrityLabel(integrity: DemoModelEntry["integrity"]) {
  if (!integrity) return "Nicht geprüft";
  return integrity === "bestanden" ? "Integritätsprüfung bestanden" : "Integritätsprüfung fehlgeschlagen";
}

/** Compact list entry, reused from the locked ModelListItem shape but with a demo tag. */
function DemoModelListItem({
  model,
  onOpen,
}: {
  model: DemoModelEntry;
  onOpen: () => void;
}) {
  const subtitle = [
    compatibilityLabel(model.compatible),
    model.loadState === "downloading" || model.loadState === "paused"
      ? `${model.downloadProgress ?? 0}% geladen`
      : undefined,
    model.size,
  ]
    .filter(Boolean)
    .join(", ");
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
      chevron
      onClick={onOpen}
    />
  );
}

export function ModelsDemoSection() {
  const [models, setModels] = useState<DemoModelEntry[]>(initialDemoModels);
  const [openId, setOpenId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const timers = useRef<Record<string, number>>({});

  useEffect(() => {
    return () => {
      Object.values(timers.current).forEach((t) => window.clearInterval(t));
    };
  }, []);

  const update = (id: string, patch: Partial<DemoModelEntry>) => {
    setModels((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  };

  const clearTimer = (id: string) => {
    const timer = timers.current[id];
    if (timer) {
      window.clearInterval(timer);
      delete timers.current[id];
    }
  };

  const startDownloadTimer = (id: string) => {
    clearTimer(id);
    timers.current[id] = window.setInterval(() => {
      setModels((prev) =>
        prev.map((m) => {
          if (m.id !== id || m.loadState !== "downloading") return m;
          const next = Math.min(100, (m.downloadProgress ?? 0) + 10);
          if (next >= 100) {
            window.clearInterval(timers.current[id]);
            delete timers.current[id];
            return { ...m, loadState: "not_loaded", downloadProgress: undefined, integrity: "bestanden" };
          }
          return { ...m, downloadProgress: next };
        }),
      );
    }, 700);
  };

  const report = (message: string) => setConfirmation(message);

  const load = (m: DemoModelEntry) => {
    update(m.id, { loadState: "loading" });
    window.setTimeout(() => {
      update(m.id, { loadState: "ready" });
      report(`"${m.name}" wurde im Demozustand geladen. ${DESIGN_STATE_ACTION}`);
    }, 600);
  };

  const unload = (m: DemoModelEntry) => {
    update(m.id, { loadState: "not_loaded" });
    report(`"${m.name}" wurde im Demozustand entladen. ${DESIGN_STATE_ACTION}`);
  };

  const startDownload = (m: DemoModelEntry) => {
    update(m.id, { loadState: "downloading", downloadProgress: 0, errorKind: undefined });
    startDownloadTimer(m.id);
    report(`Download von "${m.name}" wurde im Demozustand gestartet. ${DESIGN_STATE_ACTION}`);
  };

  const pauseDownload = (m: DemoModelEntry) => {
    clearTimer(m.id);
    update(m.id, { loadState: "paused" });
    report(`Download von "${m.name}" wurde im Demozustand pausiert. ${DESIGN_STATE_ACTION}`);
  };

  const resumeDownload = (m: DemoModelEntry) => {
    update(m.id, { loadState: "downloading" });
    startDownloadTimer(m.id);
    report(`Download von "${m.name}" wurde im Demozustand fortgesetzt. ${DESIGN_STATE_ACTION}`);
  };

  const cancelDownload = (m: DemoModelEntry) => {
    clearTimer(m.id);
    update(m.id, { loadState: "not_loaded", downloadProgress: undefined });
    report(`Download von "${m.name}" wurde im Demozustand abgebrochen. ${DESIGN_STATE_ACTION}`);
  };

  const retry = (m: DemoModelEntry) => {
    if (m.errorKind === "download") {
      update(m.id, { loadState: "downloading", downloadProgress: 0, errorKind: undefined });
      startDownloadTimer(m.id);
    } else {
      update(m.id, { loadState: "loading", errorKind: undefined });
      window.setTimeout(() => update(m.id, { loadState: "ready" }), 600);
    }
    report(`Vorgang für "${m.name}" wurde im Demozustand erneut versucht. ${DESIGN_STATE_ACTION}`);
  };

  const deleteEntry = () => {
    if (!deleteId) return;
    const model = models.find((m) => m.id === deleteId);
    clearTimer(deleteId);
    setModels((prev) => prev.filter((m) => m.id !== deleteId));
    setDeleteId(null);
    setOpenId(null);
    if (model) {
      report(`"${model.name}" wurde im Demozustand gelöscht. ${DESIGN_STATE_ACTION}`);
    }
  };

  const open = models.find((m) => m.id === openId) ?? null;
  const deleteTarget = models.find((m) => m.id === deleteId) ?? null;

  return (
    <SectionEnter index={5}>
      <SectionHeader>Zustandsdemonstration</SectionHeader>
      <div className="px-4 pb-2">
        <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
      </div>
      <ListGroup>
        {models.map((m) => (
          <DemoModelListItem key={m.id} model={m} onOpen={() => setOpenId(m.id)} />
        ))}
      </ListGroup>
      <p role="status" aria-live="polite" className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
        {confirmation ?? ""}
      </p>

      <BottomSheet
        open={!!open}
        onClose={() => setOpenId(null)}
        title={open?.name ?? "Modell"}
      >
        {open ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col">
              <DetailField label="Name">{open.name}</DetailField>
              <DetailField label="Quelle">
                {open.source === "import" ? "Lokaler Import" : "Modellkatalog"}
              </DetailField>
              <DetailField label="Lokaler Zustand">
                <StatusTag
                  state={modelLoadStateTone[open.loadState]}
                  label={modelLoadStateLabel[open.loadState]}
                  dot={false}
                />
              </DetailField>
              <DetailField label="Kompatibilität">{compatibilityLabel(open.compatible)}</DetailField>
              <DetailField label="Integrität">{integrityLabel(open.integrity)}</DetailField>
              {open.size ? <DetailField label="Größe">{open.size}</DetailField> : null}
              <DetailField label="Runtime-Zustand">Nicht an eine Runtime gebunden</DetailField>
              {open.loadState === "downloading" || open.loadState === "paused" ? (
                <DetailField label="Fortschritt (Demo)">
                  <span className="inline-flex items-center gap-2">
                    <span className="h-1.5 w-24 overflow-hidden rounded-full bg-border-soft" aria-hidden>
                      <span
                        className="block h-full bg-primary"
                        style={{ width: `${open.downloadProgress ?? 0}%` }}
                      />
                    </span>
                    {open.downloadProgress ?? 0}%
                  </span>
                </DetailField>
              ) : null}
            </div>

            {open.loadState === "incompatible" ? (
              <div className="px-4">
                <InlineNotice tone="warning">
                  Dieses Beispielmodell ist als inkompatibel markiert und kann im Demozustand nicht
                  geladen werden.
                </InlineNotice>
              </div>
            ) : null}

            {open.loadState === "error" ? (
              <div className="px-4">
                <InlineNotice tone="error">
                  {open.errorKind === "download"
                    ? "Der Download ist im Demozustand fehlgeschlagen."
                    : "Das Laden ist im Demozustand fehlgeschlagen."}
                </InlineNotice>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2 px-4 pb-1">
              {open.loadState === "not_loaded" && open.compatible ? (
                <Button variant="primary" onClick={() => load(open)}>
                  Laden
                </Button>
              ) : null}
              {open.loadState === "not_loaded" && open.source === "katalog" && open.compatible ? (
                <Button onClick={() => startDownload(open)}>Download starten</Button>
              ) : null}
              {open.loadState === "ready" ? (
                <Button onClick={() => unload(open)}>Entladen</Button>
              ) : null}
              {open.loadState === "downloading" ? (
                <>
                  <Button onClick={() => pauseDownload(open)}>Download pausieren</Button>
                  <Button variant="destructive" onClick={() => cancelDownload(open)}>
                    Download abbrechen
                  </Button>
                </>
              ) : null}
              {open.loadState === "paused" ? (
                <>
                  <Button onClick={() => resumeDownload(open)}>Download fortsetzen</Button>
                  <Button variant="destructive" onClick={() => cancelDownload(open)}>
                    Download abbrechen
                  </Button>
                </>
              ) : null}
              {open.loadState === "error" ? (
                <Button onClick={() => retry(open)}>Erneut versuchen</Button>
              ) : null}
              <Button variant="destructive" onClick={() => setDeleteId(open.id)}>
                Löschen
              </Button>
            </div>
          </div>
        ) : null}
      </BottomSheet>

      {deleteTarget ? (
        <Dialog
          open={!!deleteTarget}
          onClose={() => setDeleteId(null)}
          title="Modell löschen"
          description={`"${deleteTarget.name}" wird im Demozustand aus dieser Beispielliste entfernt.`}
        >
          <Button onClick={() => setDeleteId(null)}>Abbrechen</Button>
          <Button variant="destructive" onClick={deleteEntry}>
            Löschen
          </Button>
        </Dialog>
      ) : (
        <Dialog open={false} onClose={() => setDeleteId(null)} title="Modell löschen">
          <Button onClick={() => setDeleteId(null)}>Abbrechen</Button>
        </Dialog>
      )}
    </SectionEnter>
  );
}

/* ------------------------------ Import wizard ----------------------------- */

type ImportStep = "auswahl" | "kompatibilitaet" | "integritaet" | "registrierung" | "fertig";

export function ImportFlow({ onDone }: { onDone: (message: string) => void }) {
  const [step, setStep] = useState<ImportStep>("auswahl");
  const [failedAt, setFailedAt] = useState<ImportStep | null>(null);

  const stepLabel: Record<ImportStep, string> = {
    auswahl: "1 von 4: Datei auswählen",
    kompatibilitaet: "2 von 4: Kompatibilitätsprüfung",
    integritaet: "3 von 4: Integritätsprüfung",
    registrierung: "4 von 4: Registrierung",
    fertig: "Abgeschlossen",
  };

  const fail = (at: ImportStep) => setFailedAt(at);
  const retry = () => setFailedAt(null);

  if (failedAt) {
    return (
      <div className="flex flex-col gap-3 px-4 pt-3">
        <p className="label-system">{stepLabel[failedAt]}</p>
        <InlineNotice tone="error">
          {failedAt === "kompatibilitaet"
            ? "Kompatibilitätsprüfung nicht bestanden (simuliert). Diese Beispieldatei gilt im Demozustand als nicht LiteRT-kompatibel."
            : "Integritätsprüfung fehlgeschlagen (simuliert). Die Prüfsumme der Beispieldatei stimmt im Demozustand nicht überein."}
        </InlineNotice>
        <div className="flex gap-2">
          <Button onClick={retry}>Erneut versuchen</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 px-4 pt-3">
      <p className="label-system">{stepLabel[step]}</p>

      {step === "auswahl" ? (
        <>
          <InlineNotice tone="info">
            Die Android-Dateiauswahl ist im Entwurfszustand nicht angebunden. Dieser Ablauf zeigt nur
            die Abfolge der Oberfläche, es wird keine reale Datei ausgewählt.
          </InlineNotice>
          <Button variant="primary" full onClick={() => setStep("kompatibilitaet")}>
            Beispieldatei auswählen (Demo)
          </Button>
        </>
      ) : null}

      {step === "kompatibilitaet" ? (
        <>
          <InlineNotice tone="info">
            Prüft die Beispieldatei im Demozustand gegen die LiteRT-Runtime.
          </InlineNotice>
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => setStep("integritaet")}>
              Bestanden simulieren
            </Button>
            <Button variant="destructive" onClick={() => fail("kompatibilitaet")}>
              Fehlschlag simulieren
            </Button>
          </div>
        </>
      ) : null}

      {step === "integritaet" ? (
        <>
          <InlineNotice tone="info">
            Prüft die Prüfsumme der Beispieldatei im Demozustand nach SHA-256.
          </InlineNotice>
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => setStep("registrierung")}>
              Bestanden simulieren
            </Button>
            <Button variant="destructive" onClick={() => fail("integritaet")}>
              Fehlschlag simulieren
            </Button>
          </div>
        </>
      ) : null}

      {step === "registrierung" ? (
        <>
          <InlineNotice tone="info">
            Registriert die Beispieldatei im Demozustand in der lokalen Modellliste.
          </InlineNotice>
          <Button
            variant="primary"
            full
            onClick={() => {
              setStep("fertig");
              onDone(`Import der Beispieldatei abgeschlossen. ${DESIGN_STATE_ACTION}`);
            }}
          >
            Registrierung abschließen
          </Button>
        </>
      ) : null}

      {step === "fertig" ? (
        <InlineNotice tone="info">
          Import abgeschlossen (Demozustand). Es wurde keine reale Gerätedatei übernommen.
        </InlineNotice>
      ) : null}
    </div>
  );
}

/* -------------------------------- Catalog --------------------------------- */

interface CatalogEntry {
  id: string;
  name: string;
  size: string;
  note: string;
}

const catalogEntries: CatalogEntry[] = [
  { id: "cat-1", name: "Katalogbeispiel Klein", size: "350 MB", note: "Katalogbeispiel" },
  { id: "cat-2", name: "Katalogbeispiel Mittel", size: "900 MB", note: "Katalogbeispiel" },
  { id: "cat-3", name: "Katalogbeispiel Groß", size: "2,1 GB", note: "Katalogbeispiel" },
];

export function CatalogBrowser({ onDone }: { onDone: (message: string) => void }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = catalogEntries.find((c) => c.id === openId) ?? null;

  return (
    <div className="flex flex-col gap-2 pt-2">
      <div className="px-4 pb-1">
        <InlineNotice tone="info">
          Katalogbeispiele, keine Empfehlung und kein Inventar. Der reale Modellkatalog ist im
          Entwurfszustand noch nicht angebunden.
        </InlineNotice>
      </div>
      <ListGroup>
        {catalogEntries.map((c) => (
          <ListRow
            key={c.id}
            title={c.name}
            subtitle={`Katalogbeispiel, keine Empfehlung und kein Inventar, ${c.size}`}
            leading={<HardDrive className="size-4" aria-hidden />}
            chevron
            onClick={() => setOpenId(c.id)}
          />
        ))}
      </ListGroup>

      <BottomSheet open={!!open} onClose={() => setOpenId(null)} title={open?.name ?? "Katalogbeispiel"}>
        {open ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col">
              <DetailField label="Name">{open.name}</DetailField>
              <DetailField label="Quelle">Modellkatalog (Beispiel)</DetailField>
              <DetailField label="Lokaler Zustand">Nicht heruntergeladen</DetailField>
              <DetailField label="Kompatibilität">Noch nicht geprüft</DetailField>
              <DetailField label="Integrität">Noch nicht geprüft</DetailField>
              <DetailField label="Größe">{open.size}</DetailField>
              <DetailField label="Runtime-Zustand">Nicht an eine Runtime gebunden</DetailField>
            </div>
            <div className="px-4 pb-1">
              <Button
                variant="primary"
                full
                onClick={() => {
                  onDone(
                    `Download von "${open.name}" wurde im Entwurfszustand ausgelöst. ${DESIGN_STATE_ACTION}`,
                  );
                  setOpenId(null);
                }}
              >
                Download starten (Demo)
              </Button>
            </div>
          </div>
        ) : null}
      </BottomSheet>
    </div>
  );
}
