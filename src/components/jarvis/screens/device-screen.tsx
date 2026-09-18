import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { InlineNotice } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { comparisonBaseline } from "@/lib/jarvis/comparison";

/**
 * Gerät: local Android and JARVIS service capability overview.
 *
 * The foreground assistant service exists in the foundation but is modified,
 * so its state is reported as a design state and never as running or stopped.
 * Device fields stay unbound: hardware support must come from real Android
 * APIs, never from assumptions, and there are no measurements here.
 *
 * Compose mapping: DeviceScreen(state, onBack), DeviceInfoRow.
 */

const UNBOUND = "Nicht gebunden";

const androidCapabilities = [
  { title: "Systemsteuerung", detail: "Systemnahe Einstellungen und Schalter." },
  { title: "App-Steuerung", detail: "Starten, Wechseln und Bedienen von Apps." },
  { title: "Bildschirm", detail: "Sichtbare Inhalte lesen und Aktionen ausführen." },
  { title: "Medien", detail: "Wiedergabe und Lautstärke." },
  { title: "Benachrichtigungen", detail: "Lesen und Beantworten." },
  { title: "Dateien", detail: "Lokale Dateien lesen und ablegen." },
];

const deviceInfo = [
  "Android-Version",
  "Gerätemodell",
  "Hardware-Beschleunigung",
  "Speicherstatus",
];

export function DeviceScreen({ onBack }: SystemDetailProps) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Gerät" subtitle="Android und Dienste" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>J.A.R.V.I.S Dienst</SectionHeader>
        <ListGroup>
          <ListRow
            title="Vordergrunddienst"
            subtitle="Für dauerhafte lokale Verfügbarkeit vorgesehen, wird überarbeitet."
            trailing={
              <StatusTag
                state="design_state"
                label={comparisonBaseline.labels.backgroundService}
                dot={false}
              />
            }
          />
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Der Dienstzustand wird erst aus dem System gelesen. Es wird hier weder ein laufender
          noch ein gestoppter Dienst behauptet.
        </p>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Android-Fähigkeiten</SectionHeader>
        <ListGroup>
          {androidCapabilities.map((row) => (
            <ListRow key={row.title} title={row.title} subtitle={row.detail} />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Fähigkeitskategorien, keine Aussage über die Unterstützung auf einem konkreten Gerät.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Geräteinformationen</SectionHeader>
        <ListGroup>
          {deviceInfo.map((field) => (
            <ListRow
              key={field}
              title={field}
              trailing={<span className="value-mono text-muted-foreground">{UNBOUND}</span>}
            />
          ))}
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={4}>
        <SectionHeader>Prüfprinzip</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Geräte- und Hardwareeigenschaften werden ausschließlich über echte Android-APIs
            ermittelt. Es wird nichts als unterstützt angenommen, und fehlende Werte bleiben
            sichtbar ungebunden.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={5}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
