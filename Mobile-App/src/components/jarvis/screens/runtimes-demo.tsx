import { useState } from "react";
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
import {
  ActionResult,
  DEMO_AREA_NOTE,
  DESIGN_STATE_ACTION,
  DetailField,
  useActionResult,
} from "@/components/jarvis/prototype-state";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Zustandsdemonstration für Sleepy-Kopplung, Vertrauensprüfung und Übergabe.
 *
 * Alles hier ist reiner React-Zustand im Speicher. Es wird keine Transport-
 * technologie, kein QR-Code, kein Kopplungscode, keine IP-Adresse und kein
 * Zertifikats-Fingerabdruck erfunden. Die Kopplungsphasen bleiben absichtlich
 * abstrakt, weil Transport und Authentifizierung in diesem Projekt noch nicht
 * festgelegt sind.
 */

/* ------------------------------ Pairing flow ------------------------------ */

export type PairingState =
  | "nicht_verbunden"
  | "kopplung_vorbereitet"
  | "gegenstelle_pruefen"
  | "bestaetigung_erforderlich"
  | "verbunden"
  | "fehler";

const pairingLabel: Record<PairingState, string> = {
  nicht_verbunden: "Nicht verbunden",
  kopplung_vorbereitet: "Kopplung vorbereitet",
  gegenstelle_pruefen: "Gegenstelle prüfen",
  bestaetigung_erforderlich: "Bestätigung erforderlich",
  verbunden: "Verbunden",
  fehler: "Fehler",
};

const pairingTone: Record<PairingState, SystemState> = {
  nicht_verbunden: "unavailable",
  kopplung_vorbereitet: "design_state",
  gegenstelle_pruefen: "design_state",
  bestaetigung_erforderlich: "design_state",
  verbunden: "ready",
  fehler: "error",
};

const pairingStepText: Record<PairingState, string> = {
  nicht_verbunden:
    "Es besteht keine Kopplung zu Sleepy. Transport und Authentifizierung sind nicht festgelegt.",
  kopplung_vorbereitet:
    "Die Kopplung wird im Demozustand vorbereitet. Es wird noch kein Kanal geöffnet und keine Identität ausgetauscht.",
  gegenstelle_pruefen:
    "Im Demozustand würde an dieser Stelle die Gegenstelle geprüft. Welche Prüfung das konkret ist (Verfahren, Kanal, Identitätsnachweis) ist in diesem Projekt noch nicht festgelegt.",
  bestaetigung_erforderlich:
    "Im Demozustand würde hier eine ausdrückliche Bestätigung verlangt, bevor eine Kopplung als vertrauenswürdig gilt.",
  verbunden:
    "Demozustand: Kopplung als abgeschlossen markiert. Es wurde keine reale Verbindung aufgebaut und keine Authentifizierung durchgeführt.",
  fehler:
    "Demozustand: Die Kopplung ist im simulierten Ablauf fehlgeschlagen.",
};

const nextPairingStage: Partial<Record<PairingState, PairingState>> = {
  kopplung_vorbereitet: "gegenstelle_pruefen",
  gegenstelle_pruefen: "bestaetigung_erforderlich",
  bestaetigung_erforderlich: "verbunden",
};

export function SleepyPairingSection() {
  const [pairing, setPairing] = useState<PairingState>("nicht_verbunden");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const { message, report } = useActionResult();

  const openPairing = () => {
    setPairing("kopplung_vorbereitet");
    setSheetOpen(true);
  };

  const advance = () => {
    const next = nextPairingStage[pairing];
    if (!next) return;
    setPairing(next);
    if (next === "verbunden") {
      report(`Demozustand: Sleepy als gekoppelt markiert. ${DESIGN_STATE_ACTION}`);
    }
  };

  const failPairing = () => {
    setPairing("fehler");
  };

  const cancelPairing = () => {
    setPairing("nicht_verbunden");
    setSheetOpen(false);
    report(`Kopplung im Demozustand abgebrochen. ${DESIGN_STATE_ACTION}`);
  };

  const closeSheetAfterSuccess = () => {
    setSheetOpen(false);
  };

  const disconnect = () => {
    setPairing("nicht_verbunden");
    setDisconnectOpen(false);
    report(`Demozustand: Verbindung zu Sleepy getrennt. ${DESIGN_STATE_ACTION}`);
  };

  return (
    <SectionEnter index={6}>
      <SectionHeader>Zustandsdemonstration: Sleepy-Kopplung</SectionHeader>
      <div className="px-4 pb-2">
        <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
      </div>
      <ListGroup>
        <ListRow
          title="Kopplungszustand (Demo)"
          subtitle={pairingStepText[pairing]}
          trailing={<StatusTag state={pairingTone[pairing]} label={pairingLabel[pairing]} dot={false} />}
        />
      </ListGroup>
      <div className="flex flex-wrap gap-2 px-4 pt-3">
        {pairing === "nicht_verbunden" || pairing === "fehler" ? (
          <Button variant="primary" onClick={openPairing}>
            Sleepy koppeln
          </Button>
        ) : null}
        {pairing === "verbunden" ? (
          <Button variant="destructive" onClick={() => setDisconnectOpen(true)}>
            Verbindung trennen
          </Button>
        ) : null}
      </div>
      <ActionResult message={message} />

      <BottomSheet
        open={sheetOpen}
        onClose={cancelPairing}
        title="Sleepy koppeln (Demozustand)"
      >
        <div className="flex flex-col gap-3">
          <div className="px-4">
            <InlineNotice tone="warning">
              Transport und Authentifizierung sind in diesem Projekt noch nicht festgelegt. Dieser
              Ablauf zeigt nur die Abfolge abstrakter Phasen, es wird kein Kopplungscode, kein
              QR-Code, keine IP-Adresse und kein Zertifikats-Fingerabdruck angezeigt oder erzeugt.
            </InlineNotice>
          </div>
          <ListGroup>
            <ListRow
              title="Aktuelle Phase"
              trailing={<StatusTag state={pairingTone[pairing]} label={pairingLabel[pairing]} dot={false} />}
            />
          </ListGroup>
          <p className="px-4 text-[12px] leading-5 text-subtle-foreground">
            {pairingStepText[pairing]}
          </p>

          {pairing === "verbunden" ? (
            <div className="px-4">
              <InlineNotice tone="info">
                Es wurde keine reale Verbindung erzeugt. Dieser Zustand dient nur der Darstellung
                der vorgesehenen Abfolge.
              </InlineNotice>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2 px-4 pb-1">
            {pairing !== "verbunden" && pairing !== "fehler" ? (
              <Button variant="primary" onClick={advance}>
                Nächste Phase (Demo)
              </Button>
            ) : null}
            {pairing !== "verbunden" && pairing !== "fehler" ? (
              <Button variant="destructive" onClick={failPairing}>
                Fehlschlag simulieren
              </Button>
            ) : null}
            {pairing === "verbunden" ? (
              <Button variant="primary" onClick={closeSheetAfterSuccess}>
                Schließen
              </Button>
            ) : null}
            {pairing === "fehler" ? (
              <Button onClick={() => setPairing("kopplung_vorbereitet")}>Erneut versuchen</Button>
            ) : null}
            <Button onClick={cancelPairing}>Abbrechen</Button>
          </div>
        </div>
      </BottomSheet>

      <Dialog
        open={disconnectOpen}
        onClose={() => setDisconnectOpen(false)}
        title="Verbindung trennen"
        description="Die im Demozustand gekoppelte Sleepy-Verbindung wird getrennt. Es handelt sich um lokalen Zustand, keine reale Trennung."
      >
        <Button onClick={() => setDisconnectOpen(false)}>Abbrechen</Button>
        <Button variant="destructive" onClick={disconnect}>
          Trennen
        </Button>
      </Dialog>
    </SectionEnter>
  );
}

/* ---------------------------- Trust inspection ----------------------------- */

export function TrustInspectionSection() {
  return (
    <SectionEnter index={7}>
      <SectionHeader>Vertrauensprüfung (Nur-Lesen)</SectionHeader>
      <div className="flex flex-col">
        <DetailField label="Runtime-Name">Sleepy</DetailField>
        <DetailField label="Vertrauenszustand">Nicht gebunden</DetailField>
        <DetailField label="Ausführungsrolle">Optionale vertraute Ausführungsumgebung</DetailField>
        <DetailField label="Identität">Nicht gebunden</DetailField>
        <DetailField label="Fähigkeiten">Noch nicht festgelegt</DetailField>
        <DetailField label="Erlaubter Übergabe-Umfang">Noch nicht festgelegt</DetailField>
      </div>
      <p className="px-4 pt-1 text-[11px] leading-4 text-muted-foreground">
        Diese Felder zeigen die vorgesehene Struktur einer Vertrauensprüfung. Es sind keine
        erfundenen Werte eingetragen, solange keine echte Kopplung besteht.
      </p>
    </SectionEnter>
  );
}

/* ------------------------------ Handoff review ----------------------------- */

type HandoffState = "entwurf" | "bestaetigt" | "abgebrochen";

export function HandoffReviewSection() {
  const [state, setState] = useState<HandoffState>("entwurf");
  const { message, report } = useActionResult();

  const confirm = () => {
    setState("bestaetigt");
    report(`Übergabe-Ansicht im Demozustand bestätigt, es fand keine Übergabe statt. ${DESIGN_STATE_ACTION}`);
  };

  const cancel = () => {
    setState("abgebrochen");
    report(`Übergabe-Ansicht im Demozustand abgebrochen. ${DESIGN_STATE_ACTION}`);
  };

  const reset = () => setState("entwurf");

  return (
    <SectionEnter index={8}>
      <SectionHeader>Übergabe-Ansicht (Nur lokale Demo, keine Ausführung)</SectionHeader>
      <div className="px-4 pb-2">
        <InlineNotice tone="info">
          Diese Ansicht zeigt nur, wie eine Übergabe zur Prüfung dargestellt würde. Es findet keine
          entfernte Ausführung statt.
        </InlineNotice>
      </div>
      <div className="flex flex-col">
        <DetailField label="Aufgabe / Ziel">Beispielziel einer Übergabe (Demo)</DetailField>
        <DetailField label="Freigegebener Kontext">Nur ausdrücklich freigegebene Beispielinhalte</DetailField>
        <DetailField label="Privacy-Modus">Wird aus dem aufrufenden Kontext übernommen</DetailField>
        <DetailField label="Limits">Schritt-, Zeit- und Werkzeuggrenzen (Beispielstruktur)</DetailField>
        <DetailField label="Erwartetes Ergebnis">Vereinbarte Form der Antwort (Beispielstruktur)</DetailField>
        <DetailField label="Ziel-Runtime">Sleepy (Demozustand, nicht verbunden)</DetailField>
      </div>

      {state === "entwurf" ? (
        <div className="flex flex-wrap gap-2 px-4 pt-2 pb-1">
          <Button variant="primary" onClick={confirm}>
            Bestätigen
          </Button>
          <Button variant="destructive" onClick={cancel}>
            Abbrechen
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 px-4 pt-2 pb-1">
          <InlineNotice tone={state === "bestaetigt" ? "info" : "warning"}>
            {state === "bestaetigt"
              ? "Demozustand bestätigt. Es wurde keine Übergabe ausgeführt und keine Runtime angesprochen."
              : "Demozustand abgebrochen. Es wurde keine Übergabe ausgeführt."}
          </InlineNotice>
          <div>
            <Button onClick={reset}>Zurücksetzen</Button>
          </div>
        </div>
      )}
      <ActionResult message={message} />
    </SectionEnter>
  );
}
