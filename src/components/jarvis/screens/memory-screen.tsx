import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { Button, BottomSheet, Dialog, EmptyState, TextInput } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import {
  DESIGN_STATE_ACTION,
  DEMO_AREA_NOTE,
  ActionResult,
  DetailField,
  useActionResult,
} from "@/components/jarvis/prototype-state";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Memory: transparency surface for what JARVIS may remember and why.
 *
 * Memory is a layered system, not a fact list: working context, recent
 * candidates, candidates and confirmed facts, each with provenance. No entry
 * source is bound here, so the baseline section shows no counts and no
 * entries. A separate, clearly labelled demonstration section holds example
 * entries so the detail pattern and its frontend-only actions can be
 * inspected without pretending any of it is device data.
 *
 * Compose mapping: MemoryScreen(state, onBack), MemoryListItem,
 * MemoryDetailSheet.
 */

/* --------------------------- Future data contract ------------------------ */

/** Layer an entry belongs to. */
export type MemoryLayer = "working" | "recent" | "candidate" | "confirmed";

/** Where the content came from. Always reported, never guessed. */
export type MemoryProvenance =
  | "user_statement"
  | "conversation"
  | "tool_result"
  | "observation"
  | "inference"
  | "import"
  | "profile"
  | "system";

/** How far an entry's validity reaches. */
export type MemoryScope = "session" | "device" | "account" | "global";

/** How sensitive the stored content is. */
export type MemorySensitivity = "normal" | "sensitive" | "confidential";

/** Confirmation status within the memory workflow. */
export type MemoryConfirmationStatus = "unconfirmed" | "confirmed" | "corrected" | "discarded";

/** Reusable entry shape for later real data. Deliberately unpopulated. */
export interface MemoryEntry {
  id: string;
  layer: MemoryLayer;
  /** Subject of the entry, for example a person, a place or a preference. */
  subject?: string;
  /** Stored value or short summary of the entry. */
  summary: string;
  state: SystemState;
  provenance: MemoryProvenance;
  /** Only when a real confidence value exists. */
  confidence?: number;
  createdAt?: string;
  updatedAt?: string;
  /** Set when a newer entry replaced this one. */
  supersededBy?: string;
  /** How far the entry's validity reaches. */
  scope?: MemoryScope;
  /** How sensitive the stored content is. */
  sensitivity?: MemorySensitivity;
  /** Where the workflow currently stands. */
  confirmationStatus?: MemoryConfirmationStatus;
  /** Id and short label of an entry this one replaces or corrects. */
  supersedes?: { id: string; label: string };
  /** Short reference to the originating context, if one exists. */
  sourceReference?: string;
  /** Free-text note added when the entry was replaced (supersede action). */
  supersedeNote?: string;
}

/** Compact list entry for later real memory data. */
export function MemoryListItem({
  entry,
  onClick,
}: {
  entry: MemoryEntry;
  onClick?: () => void;
}) {
  return (
    <ListRow
      title={entry.subject ? `${entry.subject}: ${entry.summary}` : entry.summary}
      subtitle={provenanceLabel[entry.provenance]}
      trailing={<StatusTag state={entry.state} dot={false} />}
      chevron={!!onClick}
      {...(onClick ? { onClick } : {})}
    />
  );
}

const provenanceLabel: Record<MemoryProvenance, string> = {
  user_statement: "Explizite Nutzerangabe",
  conversation: "Konversation",
  tool_result: "Tool-Ergebnis",
  observation: "Beobachtung",
  inference: "Inferenz",
  import: "Import",
  profile: "Profil",
  system: "System",
};

const layerLabel: Record<MemoryLayer, string> = {
  working: "Arbeitskontext",
  recent: "Kürzlich",
  candidate: "Kandidat",
  confirmed: "Bestätigt",
};

const scopeLabel: Record<MemoryScope, string> = {
  session: "Nur diese Sitzung",
  device: "Dieses Gerät",
  account: "Konto",
  global: "Global",
};

const sensitivityLabel: Record<MemorySensitivity, string> = {
  normal: "Normal",
  sensitive: "Sensibel",
  confidential: "Vertraulich",
};

const confirmationStatusLabel: Record<MemoryConfirmationStatus, string> = {
  unconfirmed: "Unbestätigt",
  confirmed: "Bestätigt",
  corrected: "Korrigiert",
  discarded: "Verworfen",
};

/* -------------------------------- Content -------------------------------- */

const layers: { title: string; detail: string }[] = [
  {
    title: "Arbeitskontext",
    detail: "Was für den laufenden Vorgang gerade gebraucht wird.",
  },
  { title: "Kürzlich", detail: "Kurzfristige Inhalte, die noch nicht bewertet sind." },
  { title: "Kandidaten", detail: "Vorgemerkte Inhalte, noch keine bestätigten Fakten." },
  { title: "Bestätigt", detail: "Bestätigte Fakten mit Herkunft und Korrekturweg." },
];

const provenanceRows: { title: string; detail: string }[] = [
  { title: "Explizite Nutzerangabe", detail: "Direkt mitgeteilte Information." },
  { title: "Konversation", detail: "Aus einem Gespräch abgeleitete Angabe." },
  { title: "Tool-Ergebnis", detail: "Ergebnis eines ausgeführten Werkzeugs." },
  { title: "Beobachtung", detail: "Aus zulässiger Beobachtung gewonnene Angabe." },
  { title: "Inferenz", detail: "Abgeleitet, nicht direkt gesagt." },
  { title: "Import", detail: "Aus einer übernommenen Quelle." },
  { title: "Profil", detail: "Dauerhafte Angaben zur Person oder zum Gerät." },
  { title: "System", detail: "Vom System gesetzte Angabe." },
];

const rules: { title: string; detail: string }[] = [
  { title: "Nicht jeder Satz wird Memory", detail: "Relevanz entscheidet, nicht Menge." },
  {
    title: "Privacy-Inhalte erzeugen kein Memory",
    detail: "Geschützte Inhalte werden nicht extrahiert.",
  },
  {
    title: "Kandidaten sind keine Fakten",
    detail: "Erst nach Bestätigung zählt ein Eintrag als Faktum.",
  },
  {
    title: "Bestätigtes bleibt korrigierbar",
    detail: "Fakten können widerrufen oder ersetzt werden.",
  },
  {
    title: "Kein interner Gedankengang",
    detail: "Zwischenüberlegungen des Modells werden nicht gespeichert.",
  },
];

/** Example entries for the demonstration section. UI examples, no device data. */
const demoSeed: MemoryEntry[] = [
  {
    id: "demo-1",
    layer: "candidate",
    subject: "Bevorzugter Name",
    summary: "Möchte mit Vornamen angesprochen werden.",
    state: "design_state",
    provenance: "user_statement",
    confidence: 0.72,
    createdAt: "12.03.2024",
    scope: "account",
    sensitivity: "normal",
    confirmationStatus: "unconfirmed",
    sourceReference: "Gespräch vom 12.03.2024, Abschnitt Begrüßung",
  },
  {
    id: "demo-2",
    layer: "confirmed",
    subject: "Zeitzone",
    summary: "Europe/Berlin.",
    state: "design_state",
    provenance: "profile",
    createdAt: "02.01.2024",
    updatedAt: "02.01.2024",
    scope: "device",
    sensitivity: "normal",
    confirmationStatus: "confirmed",
  },
  {
    id: "demo-3",
    layer: "confirmed",
    subject: "Kalenderzugriff",
    summary: "Erlaubt für Terminvorschläge, ersetzt frühere Einschränkung.",
    state: "design_state",
    provenance: "tool_result",
    createdAt: "18.02.2024",
    updatedAt: "05.04.2024",
    scope: "device",
    sensitivity: "sensitive",
    confirmationStatus: "corrected",
    supersedes: { id: "demo-3-alt", label: "Kalenderzugriff: nur lesend" },
    sourceReference: "Einstellungen, Verlaufseintrag Berechtigungen",
  },
  {
    id: "demo-4",
    layer: "recent",
    subject: "Letzter Ort",
    summary: "Erwähnung eines Cafes im Gespräch, noch nicht bewertet.",
    state: "design_state",
    provenance: "conversation",
    createdAt: "heute",
    scope: "session",
    sensitivity: "normal",
    confirmationStatus: "unconfirmed",
  },
];

/* ------------------------------ Detail sheet ------------------------------ */

function MemoryDetailSheet({
  entry,
  onClose,
  onConfirm,
  onCorrect,
  onDiscard,
  onSupersede,
  onShowProvenance,
}: {
  entry: MemoryEntry | null;
  onClose: () => void;
  onConfirm: (id: string) => void;
  onCorrect: (id: string, next: string) => void;
  onDiscard: (id: string) => void;
  onSupersede: (id: string, note: string) => void;
  onShowProvenance: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [supersedeOpen, setSupersedeOpen] = useState(false);
  const [supersedeNote, setSupersedeNote] = useState("");
  const [provenanceOpen, setProvenanceOpen] = useState(false);

  if (!entry) return null;

  const resetLocal = () => {
    setEditing(false);
    setDraft("");
    setConfirmDiscard(false);
    setSupersedeOpen(false);
    setSupersedeNote("");
    setProvenanceOpen(false);
  };

  return (
    <BottomSheet
      open={!!entry}
      onClose={() => {
        resetLocal();
        onClose();
      }}
      title="Memory-Eintrag"
    >
      <DetailField label="Subjekt">{entry.subject ?? "Ohne Subjekt"}</DetailField>
      <DetailField label="Wert / Zusammenfassung">
        {editing ? (
          <TextInput
            id={`correct-${entry.id}`}
            label="Korrigierter Wert"
            value={draft}
            onChange={setDraft}
          />
        ) : (
          entry.summary
        )}
      </DetailField>
      <DetailField label="Ebene">{layerLabel[entry.layer]}</DetailField>
      <DetailField label="Herkunft">{provenanceLabel[entry.provenance]}</DetailField>
      {entry.confidence !== undefined ? (
        <DetailField label="Konfidenz">{Math.round(entry.confidence * 100)} %</DetailField>
      ) : null}
      {entry.scope ? <DetailField label="Geltungsbereich">{scopeLabel[entry.scope]}</DetailField> : null}
      {entry.sensitivity ? (
        <DetailField label="Sensibilität">{sensitivityLabel[entry.sensitivity]}</DetailField>
      ) : null}
      {entry.createdAt ? <DetailField label="Erstellt">{entry.createdAt}</DetailField> : null}
      {entry.updatedAt ? <DetailField label="Aktualisiert">{entry.updatedAt}</DetailField> : null}
      {entry.confirmationStatus ? (
        <DetailField label="Bestätigungsstatus">
          {confirmationStatusLabel[entry.confirmationStatus]}
        </DetailField>
      ) : null}
      {entry.supersedes ? (
        <DetailField label="Ersetzt">{entry.supersedes.label}</DetailField>
      ) : null}
      {entry.supersedeNote ? (
        <DetailField label="Ersetzungsnotiz">{entry.supersedeNote}</DetailField>
      ) : null}
      {entry.sourceReference ? (
        <DetailField label="Quellverweis">{entry.sourceReference}</DetailField>
      ) : null}

      <div className="flex flex-wrap gap-2 px-4 pt-3">
        {editing ? (
          <>
            <Button
              variant="primary"
              onClick={() => {
                onCorrect(entry.id, draft || entry.summary);
                setEditing(false);
              }}
            >
              Korrektur speichern
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Abbrechen
            </Button>
          </>
        ) : (
          <>
            <Button variant="primary" onClick={() => onConfirm(entry.id)}>
              Kandidat bestätigen
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setDraft(entry.summary);
                setEditing(true);
              }}
            >
              Korrigieren
            </Button>
            <Button variant="secondary" onClick={() => setSupersedeOpen(true)}>
              Ersetzen
            </Button>
            <Button variant="secondary" onClick={() => setProvenanceOpen(true)}>
              Herkunft ansehen
            </Button>
            <Button variant="destructive" onClick={() => setConfirmDiscard(true)}>
              Verwerfen
            </Button>
          </>
        )}
      </div>


      <Dialog
        open={confirmDiscard}
        onClose={() => setConfirmDiscard(false)}
        title="Eintrag verwerfen?"
        description="Der Eintrag wird im Demonstrationszustand als verworfen markiert. Kein Memory-Speicher wird geschrieben."
      >
        <Button variant="secondary" onClick={() => setConfirmDiscard(false)}>
          Abbrechen
        </Button>
        <Button
          variant="destructive"
          onClick={() => {
            onDiscard(entry.id);
            setConfirmDiscard(false);
            resetLocal();
            onClose();
          }}
        >
          Verwerfen
        </Button>
      </Dialog>

      <BottomSheet
        open={supersedeOpen}
        onClose={() => setSupersedeOpen(false)}
        title="Eintrag ersetzen"
      >
        <TextInput
          id={`supersede-${entry.id}`}
          label="Kurze Notiz zur Ersetzung"
          placeholder="Zum Beispiel: durch aktuellere Angabe ersetzt"
          value={supersedeNote}
          onChange={setSupersedeNote}
        />
        <div className="flex gap-2 px-4 pt-3">
          <Button
            variant="primary"
            onClick={() => {
              onSupersede(entry.id, supersedeNote);
              setSupersedeOpen(false);
              setSupersedeNote("");
            }}
          >
            Ersetzung übernehmen
          </Button>
          <Button variant="secondary" onClick={() => setSupersedeOpen(false)}>
            Abbrechen
          </Button>
        </div>
      </BottomSheet>

      <BottomSheet
        open={provenanceOpen}
        onClose={() => setProvenanceOpen(false)}
        title="Herkunft im Detail"
      >
        <DetailField label="Herkunftsart">{provenanceLabel[entry.provenance]}</DetailField>
        <DetailField label="Erstellt">{entry.createdAt ?? "Unbekannt"}</DetailField>
        <DetailField label="Quellverweis">
          {entry.sourceReference ?? "Kein Quellverweis hinterlegt."}
        </DetailField>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Kompakte Herkunftsansicht ohne Gedankengang und ohne Rohinhalte der Quelle.
        </p>
      </BottomSheet>
    </BottomSheet>
  );
}

/* --------------------------------- Screen --------------------------------- */

export function MemoryScreen({ onBack }: DetailScreenProps) {
  /**
   * No memory source is bound in this phase. The empty list describes the
   * missing binding, not a verified absence of entries on a real device.
   */
  const entries: MemoryEntry[] = [];

  const [demoEntries, setDemoEntries] = useState<MemoryEntry[]>(demoSeed);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { message, report } = useActionResult();

  const selected = demoEntries.find((e) => e.id === selectedId) ?? null;

  const updateEntry = (id: string, patch: Partial<MemoryEntry>) => {
    setDemoEntries((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  };

  const handleConfirm = (id: string) => {
    updateEntry(id, { confirmationStatus: "confirmed", layer: "confirmed" });
    report(`Kandidat als bestätigt markiert. ${DESIGN_STATE_ACTION}`);
  };

  const handleCorrect = (id: string, next: string) => {
    updateEntry(id, { summary: next, confirmationStatus: "corrected" });
    report(`Wert lokal korrigiert. ${DESIGN_STATE_ACTION}`);
  };

  const handleDiscard = (id: string) => {
    updateEntry(id, { confirmationStatus: "discarded" });
    report(`Eintrag als verworfen markiert. ${DESIGN_STATE_ACTION}`);
  };

  const handleSupersede = (id: string, note: string) => {
    updateEntry(id, {
      confirmationStatus: "corrected",
      supersedeNote: note || "Ohne zusätzliche Notiz.",
      updatedAt: "gerade eben",
    });
    report(`Eintrag als ersetzt markiert. ${DESIGN_STATE_ACTION}`);
  };

  const handleShowProvenance = () => {
    // Herkunftsansicht ist Teil des Sheets, keine zusätzliche Statusänderung.
  };

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader
          title="Memory"
          subtitle="Gedächtnis und Herkunft"
          onBack={onBack}
          backLabel={MORE_BACK_LABEL}
        />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Speicherbereiche</SectionHeader>
        <ListGroup>
          {layers.map((l) => (
            <ListRow key={l.title} title={l.title} subtitle={l.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Aktueller Zustand</SectionHeader>
        {entries.length === 0 ? (
          <div className="px-4">
            <EmptyState
              title="Keine Memory-Daten angebunden"
              body="Der Memory-Speicher ist im Entwurfszustand noch nicht an eine Runtime gebunden. Einträge, Herkunft und Bestätigung werden später hier verwaltet."
            />
          </div>
        ) : (
          <ListGroup>
            {entries.map((e) => (
              <MemoryListItem key={e.id} entry={e} />
            ))}
          </ListGroup>
        )}
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Herkunft</SectionHeader>
        <ListGroup>
          {provenanceRows.map((p) => (
            <ListRow key={p.title} title={p.title} subtitle={p.detail} />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Beschreibt mögliche Quellen eines Eintrags, keine vorhandenen Einträge.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Regeln</SectionHeader>
        <ListGroup>
          {rules.map((r) => (
            <ListRow key={r.title} title={r.title} subtitle={r.detail} />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Zustandsdemonstration</SectionHeader>
        <p className="px-4 pb-2 text-[11px] leading-4 text-muted-foreground">{DEMO_AREA_NOTE}</p>
        <ListGroup>
          {demoEntries.map((e) => (
            <MemoryListItem key={e.id} entry={e} onClick={() => setSelectedId(e.id)} />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Antippen öffnet das Detailmuster mit Aktionen zum Ausprobieren, ohne echten
          Memory-Zugriff.
        </p>
        <ActionResult message={message} />
      </SectionEnter>

      <SectionEnter index={6}>
        <SectionHeader>Weiterentwicklung</SectionHeader>
        <ListGroup>
          <ListRow
            title="Konsolidierung"
            subtitle="Zusammenführen und Bereinigen bestätigter Inhalte."
            trailing={
              <StatusTag
                state="design_state"
                label="Noch nicht vollständig implementiert"
                dot={false}
              />
            }
          />
          <ListRow
            title="Decay"
            subtitle="Alterung und Abwertung nicht mehr belegter Inhalte."
            trailing={<StatusTag state="design_state" dot={false} />}
          />
          <ListRow
            title="Autonomie-Budget"
            subtitle="Grenze dafür, wie viel JARVIS selbstständig merken darf."
            trailing={<StatusTag state="design_state" dot={false} />}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Zielarchitektur, im Entwurfszustand noch keine bedienbaren Regler.
        </p>
      </SectionEnter>

      <SectionEnter index={7}>
        <DesignStateNote />
      </SectionEnter>

      <MemoryDetailSheet
        entry={selected}
        onClose={() => setSelectedId(null)}
        onConfirm={handleConfirm}
        onCorrect={handleCorrect}
        onDiscard={handleDiscard}
        onSupersede={handleSupersede}
        onShowProvenance={handleShowProvenance}
      />
    </ScrollBody>
  );
}
