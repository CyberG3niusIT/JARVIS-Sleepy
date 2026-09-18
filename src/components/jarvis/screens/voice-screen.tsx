import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { InlineNotice } from "@/components/jarvis/controls";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";

/**
 * Voice: configuration and status surface for local speech interaction.
 *
 * Voice is REPLACE in the mobile IA. The OpenDroid voice foundation exists,
 * but the mobile target is local first and is not bound here. No microphone
 * permission state, no wake word, no engine, no voice, no latency.
 *
 * Compose mapping: VoiceScreen(state, onBack).
 */

const UNBOUND = "Nicht gebunden";
const UNBOUND_STATUS = "Status nicht gebunden";

export function VoiceScreen({ onBack }: DetailScreenProps) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader
          title="Voice"
          subtitle="Sprachein- und ausgabe"
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
        <SectionHeader>Wake Word</SectionHeader>
        <ListGroup>
          <ListRow
            title="Aktivierung"
            trailing={<StatusTag state="design_state" dot={false} />}
          />
          <ListRow
            title="Engine"
            trailing={<StatusTag state="design_state" label={UNBOUND} dot={false} />}
          />
          <ListRow
            title="Schlüsselwort"
            trailing={<StatusTag state="design_state" label={UNBOUND} dot={false} />}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Die Erkennung des Schlüsselworts soll lokal auf dem Gerät laufen. Engine und
          Schlüsselwort werden erst festgelegt, wenn die mobile Sprachschicht steht.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Spracherkennung</SectionHeader>
        <ListGroup>
          <ListRow title="STT" trailing={<StatusTag state="not_implemented" dot={false} />} />
          <ListRow
            title="Sprache"
            subtitle="Produktsprache der Anwendung, kein erkannter Laufzeitwert."
            trailing={<span className="value-mono">Deutsch</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Ziel ist eine lokale Transkription auf dem Gerät. Modell, Laufzeit und Güte
          werden erst angezeigt, wenn sie wirklich gemessen werden.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Sprachausgabe</SectionHeader>
        <ListGroup>
          <ListRow title="TTS" trailing={<StatusTag state="not_implemented" dot={false} />} />
          <ListRow
            title="Stimme"
            trailing={<StatusTag state="design_state" label={UNBOUND} dot={false} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Privacy</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Sprachaufnahme muss dem zentralen PrivacyGate folgen. In PRIVACY sind
            geschützte Mikrofon- und STT-Pfade gesperrt, PRIVACY_LOCK kann strengere
            Grenzen erzwingen. Das Gate ist im Entwurfszustand noch nicht verdrahtet.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
