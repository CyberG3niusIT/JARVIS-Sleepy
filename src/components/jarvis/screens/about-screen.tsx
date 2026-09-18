import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import {
  DesignStateNote,
  DetailHeader,
  MORE_BACK_LABEL,
  type DetailScreenProps,
} from "@/components/jarvis/screens/detail-header";

/**
 * Über J.A.R.V.I.S: product, build and license information.
 *
 * No release version exists in the prototype baseline, so none is invented.
 * Only the verified license fact of the OpenDroid foundation is shown.
 *
 * Compose mapping: AboutScreen(state, onBack).
 */

export function AboutScreen({ onBack }: DetailScreenProps) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader
          title="Über J.A.R.V.I.S"
          subtitle="Produktinformationen"
          onBack={onBack}
          backLabel={MORE_BACK_LABEL}
        />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Produkt</SectionHeader>
        <ListGroup>
          <ListRow
            title="J.A.R.V.I.S Mobile"
            subtitle="Local AI Assistant"
          />
          <ListRow title="Plattform" trailing={<span className="value-mono">Android</span>} />
          <ListRow
            title="Ausrichtung"
            trailing={<span className="value-mono">Local First</span>}
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Version</SectionHeader>
        <ListGroup>
          <ListRow title="Version" trailing={<StatusTag state="design_state" dot={false} />} />
          <ListRow
            title="Build-Version"
            trailing={<StatusTag state="design_state" label="Nicht gebunden" dot={false} />}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Für J.A.R.V.I.S Mobile liegt in dieser Grundlage keine geprüfte Release-Version
          vor, deshalb wird hier keine Versionsnummer angezeigt.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Basis</SectionHeader>
        <ListGroup>
          <ListRow
            title="OpenDroid"
            subtitle="J.A.R.V.I.S Mobile entsteht aus der OpenDroid-Android-Grundlage und passt sie an."
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Die Grundlage betrifft die Android-Seite. J.A.R.V.I.S insgesamt ist ein eigenes
          Produkt und nicht mit OpenDroid gleichzusetzen.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Lizenzen</SectionHeader>
        <ListGroup>
          <ListRow
            title="OpenDroid Basis"
            trailing={<span className="value-mono">Apache License 2.0</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Nur geprüfte Lizenzangaben. Für J.A.R.V.I.S-eigene Anteile wird hier keine
          Lizenz behauptet.
        </p>
      </SectionEnter>

      <SectionEnter index={5}>
        <SectionHeader>Prinzip</SectionHeader>
        <p className="px-4 pt-1 text-[13px] leading-5 text-subtle-foreground">
          Local First. Deterministisch vor generativ. Keine stillen Cloud-Fallbacks.
        </p>
      </SectionEnter>

      <SectionEnter index={6}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
