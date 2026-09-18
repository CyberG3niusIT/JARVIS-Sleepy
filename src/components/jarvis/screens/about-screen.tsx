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
 * Third party attribution stays limited to the license section.
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
          Für J.A.R.V.I.S Mobile ist im Entwurfszustand noch keine geprüfte
          Release-Version hinterlegt.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Lizenzen</SectionHeader>
        <ListGroup>
          <ListRow
            title="OpenDroid"
            trailing={<span className="value-mono">Apache License 2.0</span>}
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Drittanbieter-Lizenzhinweis.
        </p>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Prinzip</SectionHeader>
        <p className="px-4 pt-1 text-[13px] leading-5 text-subtle-foreground">
          Local First. Deterministisch vor generativ. Keine stillen Cloud-Fallbacks.
        </p>
      </SectionEnter>

      <SectionEnter index={5}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
