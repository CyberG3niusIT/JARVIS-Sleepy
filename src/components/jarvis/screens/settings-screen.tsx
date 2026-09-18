import { ScrollBody } from "@/components/prototype/phone-frame";
import {
  ExecutionTag,
  ListGroup,
  ListRow,
  PrivacyTag,
  SectionHeader,
  StatusTag,
} from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Einstellungen: general product configuration.
 *
 * Owns language, appearance, storage policy, background service and the
 * general defaults. Models, permissions, logs and product information stay in
 * their own destinations and are not duplicated here. Nothing on this screen
 * writes a setting; values are product defaults or explicitly unbound.
 *
 * Compose mapping: SettingsScreen(state, onBack).
 */

const UNBOUND_STATUS = "Status nicht gebunden";

export function SettingsScreen({ onBack }: DetailScreenProps) {
  const { labels } = comparisonBaseline;

  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader
          title="Einstellungen"
          subtitle="Allgemeine Konfiguration"
          onBack={onBack}
          backLabel={MORE_BACK_LABEL}
        />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Sprache</SectionHeader>
        <ListGroup>
          <ListRow
            title="Anwendungssprache"
            subtitle="Produktsprache der Oberfläche, kein erkannter Gerätewert."
            trailing={<span className="value-mono">Deutsch</span>}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Darstellung</SectionHeader>
        <ListGroup>
          <ListRow title="Design" trailing={<span className="value-mono">Dunkel</span>} />
          <ListRow
            title="Dichte"
            subtitle="Kompakte Systemdichte des festgelegten Designsystems."
            trailing={<span className="value-mono">Kompakt</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Festgelegte Darstellung des Prototyps. Es gibt hier keinen Schalter, der eine
          Einstellung dauerhaft speichern würde.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Speicher</SectionHeader>
        <ListGroup>
          <ListRow
            title="Speicherort"
            subtitle="Lokale Anwendungsdaten werden auf dem Gerät verwaltet."
            trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
          />
          <ListRow
            title="Nutzung"
            trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Modelldateien werden unter Modelle verwaltet und hier nicht doppelt geführt.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Hintergrunddienst</SectionHeader>
        <ListGroup>
          <ListRow
            title="Assistenzdienst"
            subtitle="Der Assistenzdienst ist technisch vorgesehen, sein Laufzeitzustand ist hier nicht gebunden."
            trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Allgemein</SectionHeader>
        <ListGroup>
          <ListRow
            title="Lokale Standardausführung"
            trailing={<ExecutionTag where={comparisonBaseline.execution} />}
          />
          <ListRow
            title="Privacy-Vorgabe"
            subtitle="Aktuelle Entwurfsgrundlage, keine gespeicherte Einstellung."
            trailing={<PrivacyTag mode={comparisonBaseline.privacyMode} />}
          />
          <ListRow
            title="Cloud"
            trailing={<StatusTag state="design_state" label={labels.cloud} dot={false} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
