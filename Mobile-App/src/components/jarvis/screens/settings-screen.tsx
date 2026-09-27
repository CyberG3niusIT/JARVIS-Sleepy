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
 * writes a setting; every row carries exactly one explicit marker for what
 * kind of non-editable state it shows: a fixed product decision (FESTGELEGT),
 * an unbound prototype status (STATUS NICHT GEBUNDEN), or a pointer to the
 * destination that actually manages the value.
 *
 * Compose mapping: SettingsScreen(state, onBack).
 */

const FIXED = "Festgelegt";
const UNBOUND_STATUS = "Status nicht gebunden";
const MANAGED_MODELS = "Verwaltung in Modelle";
const MANAGED_PRIVACY = "Verwaltung in Privacy";
const MANAGED_RUNTIMES = "Verwaltung in Runtimes";
const MANAGED_PERMISSIONS = "Verwaltung in Berechtigungen";

function MarkerTag({ label }: { label: string }) {
  return <StatusTag state="design_state" label={label} dot={false} />;
}

export function SettingsScreen({ onBack }: DetailScreenProps) {
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
            subtitle="Deutsch ist die festgelegte Produktsprache der Oberfläche, kein erkannter Gerätewert."
            trailing={
              <span className="flex shrink-0 items-center gap-2">
                <span className="value-mono">Deutsch</span>
                <MarkerTag label={FIXED} />
              </span>
            }
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Darstellung</SectionHeader>
        <ListGroup>
          <ListRow
            title="Design"
            subtitle="Festgelegtes Designsystem des Prototyps."
            trailing={
              <span className="flex shrink-0 items-center gap-2">
                <span className="value-mono">Dunkel</span>
                <MarkerTag label={FIXED} />
              </span>
            }
          />
          <ListRow
            title="Dichte"
            subtitle="Kompakte Systemdichte des festgelegten Designsystems."
            trailing={
              <span className="flex shrink-0 items-center gap-2">
                <span className="value-mono">Kompakt</span>
                <MarkerTag label={FIXED} />
              </span>
            }
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
            title="Modellspeicher"
            subtitle="Modelldateien werden unter Modelle verwaltet und hier nicht doppelt geführt."
            trailing={<MarkerTag label={MANAGED_MODELS} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Hintergrunddienst</SectionHeader>
        <ListGroup>
          <ListRow
            title="Hintergrunddienst des Assistenten"
            subtitle="Der Assistenzdienst ist technisch vorgesehen, sein Laufzeitzustand ist hier nicht gebunden."
            trailing={<MarkerTag label={UNBOUND_STATUS} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Allgemein</SectionHeader>
        <ListGroup>
          <ListRow
            title="Lokale Standardausführung"
            subtitle="Anzeige des aktuellen Ausführungsorts der Vergleichsgrundlage."
            trailing={<ExecutionTag where={comparisonBaseline.execution} />}
          />
          <ListRow
            title="Privacy-Modus"
            subtitle="Wird vollständig in Privacy verwaltet, hier nur zur Einordnung angezeigt."
            trailing={
              <span className="flex shrink-0 items-center gap-2">
                <PrivacyTag mode={comparisonBaseline.privacyMode} />
                <MarkerTag label={MANAGED_PRIVACY} />
              </span>
            }
          />
          <ListRow
            title="Cloud- und Runtime-Auswahl"
            subtitle="Wird vollständig in Runtimes verwaltet."
            trailing={<MarkerTag label={MANAGED_RUNTIMES} />}
          />
          <ListRow
            title="Berechtigungen"
            subtitle="Wird vollständig in Berechtigungen verwaltet."
            trailing={<MarkerTag label={MANAGED_PERMISSIONS} />}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
