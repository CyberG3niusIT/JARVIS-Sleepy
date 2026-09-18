import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { EmptyState } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Memory: transparency surface for what JARVIS may remember and why.
 *
 * Memory is a layered system, not a fact list: working context, recent
 * candidates, candidates and confirmed facts, each with provenance. No entry
 * source is bound here, so no counts and no entries are shown.
 *
 * Compose mapping: MemoryScreen(state, onBack), MemoryListItem.
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
}

/** Compact list entry for later real memory data. */
export function MemoryListItem({ entry }: { entry: MemoryEntry }) {
  return (
    <ListRow
      title={entry.subject ? `${entry.subject}: ${entry.summary}` : entry.summary}
      subtitle={provenanceLabel[entry.provenance]}
      trailing={<StatusTag state={entry.state} dot={false} />}
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

export function MemoryScreen({ onBack }: DetailScreenProps) {
  /**
   * No memory source is bound in this phase. The empty list describes the
   * missing binding, not a verified absence of entries on a real device.
   */
  const entries: MemoryEntry[] = [];

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

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
