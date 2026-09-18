import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { BottomSheet, Button, InlineNotice, TextInput, Toggle } from "@/components/jarvis/controls";
import { SectionEnter, ValueTransition } from "@/components/jarvis/motion";
import {
  ActionResult,
  DEMO_AREA_NOTE,
  DESIGN_STATE_ACTION,
  DetailField,
  PrototypeBanner,
  useActionResult,
} from "@/components/jarvis/prototype-state";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Voice: configuration and status surface for local speech interaction.
 *
 * Voice is REPLACE in the mobile IA. The OpenDroid voice foundation exists,
 * but the mobile target is local first and is not bound here. No microphone
 * permission state, no wake word, no engine, no voice, no latency.
 *
 * This screen adds a labelled prototype state machine ("Zustandsdemonstration")
 * so every visual state of the future voice surface can be inspected, plus
 * three configuration sheets that only ever change local, in-memory values.
 * Nothing here uses or claims a real microphone, STT or TTS.
 *
 * Compose mapping: VoiceScreen(state, onBack).
 */

const UNBOUND = "Nicht gebunden";
const UNBOUND_STATUS = "Status nicht gebunden";

type VoiceState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "cancelled"
  | "permission_required"
  | "privacy_blocked"
  | "unavailable"
  | "error";

const voiceStateOrder: VoiceState[] = [
  "idle",
  "listening",
  "processing",
  "speaking",
  "cancelled",
  "permission_required",
  "privacy_blocked",
  "unavailable",
  "error",
];

const voiceStateConfig: Record<VoiceState, { label: string; tag: SystemState; desc: string }> = {
  idle: {
    label: "Idle",
    tag: "design_state",
    desc: "Keine aktive Sprachinteraktion. Ausgangszustand.",
  },
  listening: {
    label: "Hört zu",
    tag: "local",
    desc: "Beispielzustand einer Aufnahmephase. Es wird kein echtes Mikrofon verwendet.",
  },
  processing: {
    label: "Verarbeitet",
    tag: "degraded",
    desc: "Beispielzustand einer Verarbeitungsphase nach dem Ende der Aufnahme.",
  },
  speaking: {
    label: "Spricht",
    tag: "local",
    desc: "Beispielzustand einer Wiedergabephase. Es wird keine echte Sprachausgabe erzeugt.",
  },
  cancelled: {
    label: "Abgebrochen",
    tag: "design_state",
    desc: "Die Interaktion wurde durch die Person abgebrochen.",
  },
  permission_required: {
    label: "Berechtigung erforderlich",
    tag: "permission_required",
    desc: "Beispielzustand: Eine Mikrofonberechtigung fehlt. Ohne Freigabe passiert nichts.",
  },
  privacy_blocked: {
    label: "Privacy blockiert",
    tag: "privacy_blocked",
    desc: "Beispielzustand: Der Privacy-Modus sperrt geschützte Aufnahmepfade.",
  },
  unavailable: {
    label: "Runtime nicht verfügbar",
    tag: "unavailable",
    desc: "Beispielzustand: Die lokale Sprachlaufzeit ist nicht angebunden.",
  },
  error: {
    label: "Fehler",
    tag: "error",
    desc: "Beispielzustand: Der Vorgang ist fehlgeschlagen.",
  },
};

const sensitivityOptions = ["Niedrig", "Mittel", "Hoch"] as const;
const sttLanguageOptions = ["Deutsch", "Englisch"] as const;
const ttsVoiceOptions = [
  "Stimme A (UI-Beispiel)",
  "Stimme B (UI-Beispiel)",
  "Stimme C (UI-Beispiel)",
] as const;
const tempoOptions = ["Langsam", "Normal", "Schnell"] as const;
const volumeOptions = ["Leise", "Normal", "Laut"] as const;

export function VoiceScreen({ onBack }: DetailScreenProps) {
  const { message, report } = useActionResult();

  const [voiceState, setVoiceState] = useState<VoiceState>("idle");

  const [wakeWordSheetOpen, setWakeWordSheetOpen] = useState(false);
  const [wakeWordEnabled, setWakeWordEnabled] = useState(false);
  const [keyword, setKeyword] = useState("Jarvis");
  const [sensitivity, setSensitivity] = useState<(typeof sensitivityOptions)[number]>("Mittel");

  const [sttSheetOpen, setSttSheetOpen] = useState(false);
  const [sttLanguage, setSttLanguage] = useState<(typeof sttLanguageOptions)[number]>("Deutsch");
  const [sttLocalOnly, setSttLocalOnly] = useState(true);
  const [sttPunctuation, setSttPunctuation] = useState(true);

  const [ttsSheetOpen, setTtsSheetOpen] = useState(false);
  const [ttsVoice, setTtsVoice] = useState<(typeof ttsVoiceOptions)[number]>(ttsVoiceOptions[0]);
  const [tempo, setTempo] = useState<(typeof tempoOptions)[number]>("Normal");
  const [volume, setVolume] = useState<(typeof volumeOptions)[number]>("Normal");

  function goTo(next: VoiceState, note: string) {
    setVoiceState(next);
    report(`${note} ${DESIGN_STATE_ACTION}`);
  }

  function startInteraction() {
    if (
      voiceState === "permission_required" ||
      voiceState === "privacy_blocked" ||
      voiceState === "unavailable"
    ) {
      report(
        `Sprachinteraktion kann in diesem Beispielzustand nicht gestartet werden. ${DESIGN_STATE_ACTION}`,
      );
      return;
    }
    goTo("listening", "Sprachinteraktion gestartet (simuliert).");
  }

  function stopListening() {
    if (voiceState !== "listening") {
      report(`Kein aktives Zuhören zum Beenden. ${DESIGN_STATE_ACTION}`);
      return;
    }
    goTo("processing", "Zuhören beendet, Verarbeitung simuliert.");
  }

  function cancelProcessing() {
    if (voiceState !== "processing" && voiceState !== "listening") {
      report(`Keine laufende Verarbeitung zum Abbrechen. ${DESIGN_STATE_ACTION}`);
      return;
    }
    goTo("cancelled", "Verarbeitung abgebrochen.");
  }

  function stopSpeaking() {
    if (voiceState !== "speaking") {
      report(`Keine laufende Sprachausgabe zum Stoppen. ${DESIGN_STATE_ACTION}`);
      return;
    }
    goTo("idle", "Sprachausgabe gestoppt.");
  }

  const currentConfig = voiceStateConfig[voiceState];

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader
          title="Voice"
          subtitle="Spracheingabe und Sprachausgabe"
          onBack={onBack}
          backLabel={MORE_BACK_LABEL}
        />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Gesamtzustand</SectionHeader>
        <ListGroup>
          <ListRow
            title="Voice"
            subtitle="Die mobile Sprachschicht wird neu aufgebaut und ist noch nicht angebunden."
            trailing={<StatusTag state="not_implemented" />}
          />
          <ListRow
            title="Mikrofonstatus"
            trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Zustandsdemonstration</SectionHeader>
        <PrototypeBanner>{DEMO_AREA_NOTE} Kein Mikrofon, keine STT und keine TTS werden verwendet.</PrototypeBanner>

        <div className="flex items-center justify-between gap-3 px-4 pt-3">
          <span className="text-[13px] text-foreground">Aktueller Beispielzustand</span>
          <ValueTransition value={voiceState}>
            <StatusTag state={currentConfig.tag} label={currentConfig.label} />
          </ValueTransition>
        </div>
        <p className="px-4 pt-1 text-[11px] leading-4 text-muted-foreground">{currentConfig.desc}</p>

        <div className="flex flex-wrap gap-2 px-4 pt-3">
          <Button variant="primary" onClick={startInteraction}>
            Sprachinteraktion starten
          </Button>
          <Button onClick={stopListening} disabled={voiceState !== "listening"}>
            Zuhören beenden
          </Button>
          <Button onClick={cancelProcessing} disabled={voiceState !== "processing" && voiceState !== "listening"}>
            Verarbeitung abbrechen
          </Button>
          <Button onClick={stopSpeaking} disabled={voiceState !== "speaking"}>
            Sprachausgabe stoppen
          </Button>
        </div>

        <ActionResult message={message} />

        <SectionHeader>Zustand wählen</SectionHeader>
        <ListGroup>
          {voiceStateOrder.map((id) => {
            const cfg = voiceStateConfig[id];
            return (
              <ListRow
                key={id}
                title={cfg.label}
                subtitle={cfg.desc}
                selected={id === voiceState}
                trailing={<StatusTag state={cfg.tag} label={cfg.label} dot={false} />}
                onClick={() => goTo(id, `Beispielzustand "${cfg.label}" ausgewaehlt.`)}
              />
            );
          })}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Die Auswahl dient allein der Ansicht jedes moeglichen Zustands und veraendert
          nur den lokalen Vorschauzustand dieser Ansicht.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader action={<Button onClick={() => setWakeWordSheetOpen(true)}>Konfigurieren</Button>}>
          Wake Word
        </SectionHeader>
        <ListGroup>
          <ListRow
            title="Aktivierung"
            trailing={<StatusTag state="design_state" label={wakeWordEnabled ? "Aktiviert (Entwurf)" : "Deaktiviert"} dot={false} />}
          />
          <ListRow
            title="Engine"
            trailing={<StatusTag state="design_state" label={UNBOUND} dot={false} />}
          />
          <ListRow
            title="Schluesselwort"
            trailing={<span className="value-mono">{keyword || UNBOUND}</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Die Erkennung des Schluesselworts soll lokal auf dem Geraet laufen. Engine wird
          erst festgelegt, wenn die mobile Sprachschicht steht. Die Werte hier sind reine
          Oberflaechen-Beispiele.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader action={<Button onClick={() => setSttSheetOpen(true)}>Konfigurieren</Button>}>
          Spracherkennung
        </SectionHeader>
        <ListGroup>
          <ListRow title="STT" trailing={<StatusTag state="not_implemented" dot={false} />} />
          <ListRow
            title="Sprache"
            subtitle="Produktsprache der Anwendung, kein erkannter Laufzeitwert."
            trailing={<span className="value-mono">{sttLanguage}</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Ziel ist eine lokale Transkription auf dem Geraet. Modell, Laufzeit und Guete
          werden erst angezeigt, wenn sie wirklich gemessen werden.
        </p>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader action={<Button onClick={() => setTtsSheetOpen(true)}>Konfigurieren</Button>}>
          Sprachausgabe
        </SectionHeader>
        <ListGroup>
          <ListRow title="TTS" trailing={<StatusTag state="not_implemented" dot={false} />} />
          <ListRow
            title="Stimme"
            subtitle="Oberflaechen-Beispiel, kein echtes Stimmprofil."
            trailing={<span className="value-mono">{ttsVoice}</span>}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={6}>
        <SectionHeader>Privacy</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Sprachaufnahme muss dem zentralen PrivacyGate folgen. In PRIVACY sind
            geschuetzte Mikrofon- und STT-Pfade gesperrt, PRIVACY_LOCK kann strengere
            Grenzen erzwingen. Das Gate ist im Entwurfszustand noch nicht verdrahtet.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={7}>
        <DesignStateNote />
      </SectionEnter>

      <BottomSheet
        open={wakeWordSheetOpen}
        onClose={() => setWakeWordSheetOpen(false)}
        title="Wake-Word-Konfiguration"
      >
        <p className="px-4 pb-2 text-[11px] leading-4 text-muted-foreground">
          Reine Oberflaechen-Werte. Es ist noch keine Wake-Word-Engine ausgewaehlt, dieser
          Dialog legt keine fest.
        </p>
        <div className="flex min-h-12 items-center justify-between px-4">
          <span className="text-[13px] text-foreground">Aktivierung</span>
          <Toggle checked={wakeWordEnabled} onChange={setWakeWordEnabled} label="Wake Word aktivieren" />
        </div>
        <TextInput
          id="wake-word-keyword"
          label="Schluesselwort"
          value={keyword}
          onChange={setKeyword}
          placeholder="z. B. Jarvis"
        />
        <div className="px-4 pt-3">
          <span className="label-system block pb-1.5">Empfindlichkeit</span>
          <div className="flex gap-2">
            {sensitivityOptions.map((option) => (
              <Button
                key={option}
                variant={option === sensitivity ? "primary" : "secondary"}
                onClick={() => setSensitivity(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
        <div className="px-4 pt-4">
          <Button
            variant="primary"
            full
            onClick={() => {
              setWakeWordSheetOpen(false);
              report(`Wake-Word-Konfiguration gespeichert (lokal). ${DESIGN_STATE_ACTION}`);
            }}
          >
            Uebernehmen
          </Button>
        </div>
      </BottomSheet>

      <BottomSheet open={sttSheetOpen} onClose={() => setSttSheetOpen(false)} title="STT-Konfiguration">
        <p className="px-4 pb-2 text-[11px] leading-4 text-muted-foreground">
          Reine Oberflaechen-Werte. Es ist noch kein Erkennungsmodell ausgewaehlt.
        </p>
        <div className="px-4">
          <span className="label-system block pb-1.5">Sprache</span>
          <div className="flex gap-2">
            {sttLanguageOptions.map((option) => (
              <Button
                key={option}
                variant={option === sttLanguage ? "primary" : "secondary"}
                onClick={() => setSttLanguage(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
        <div className="flex min-h-12 items-center justify-between px-4 pt-3">
          <span className="text-[13px] text-foreground">Lokale Ausfuehrung</span>
          <Toggle checked={sttLocalOnly} onChange={setSttLocalOnly} label="Lokale Ausfuehrung" />
        </div>
        <div className="flex min-h-12 items-center justify-between px-4">
          <span className="text-[13px] text-foreground">Interpunktion</span>
          <Toggle checked={sttPunctuation} onChange={setSttPunctuation} label="Interpunktion" />
        </div>
        <div className="px-4 pt-4">
          <Button
            variant="primary"
            full
            onClick={() => {
              setSttSheetOpen(false);
              report(`STT-Konfiguration gespeichert (lokal). ${DESIGN_STATE_ACTION}`);
            }}
          >
            Uebernehmen
          </Button>
        </div>
      </BottomSheet>

      <BottomSheet open={ttsSheetOpen} onClose={() => setTtsSheetOpen(false)} title="TTS-Stimmenauswahl">
        <p className="px-4 pb-2 text-[11px] leading-4 text-muted-foreground">
          Neutrale Platzhalter, reine Oberflaechen-Beispiele. Es ist noch kein
          Sprachausgabe-Anbieter ausgewaehlt.
        </p>
        <ListGroup>
          {ttsVoiceOptions.map((option) => (
            <ListRow
              key={option}
              title={option}
              selected={option === ttsVoice}
              onClick={() => setTtsVoice(option)}
            />
          ))}
        </ListGroup>
        <div className="px-4 pt-3">
          <span className="label-system block pb-1.5">Tempo</span>
          <div className="flex gap-2">
            {tempoOptions.map((option) => (
              <Button
                key={option}
                variant={option === tempo ? "primary" : "secondary"}
                onClick={() => setTempo(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
        <div className="px-4 pt-3">
          <span className="label-system block pb-1.5">Lautstaerke</span>
          <div className="flex gap-2">
            {volumeOptions.map((option) => (
              <Button
                key={option}
                variant={option === volume ? "primary" : "secondary"}
                onClick={() => setVolume(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </div>
        <div className="px-4 pt-4">
          <Button
            variant="primary"
            full
            onClick={() => {
              setTtsSheetOpen(false);
              report(`TTS-Stimmenauswahl gespeichert (lokal). ${DESIGN_STATE_ACTION}`);
            }}
          >
            Uebernehmen
          </Button>
        </div>
      </BottomSheet>
    </ScrollBody>
  );
}
