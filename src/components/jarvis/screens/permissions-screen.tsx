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
 * Berechtigungen: Android access as capabilities, not onboarding checkboxes.
 *
 * The baseline only knows the generic "Berechtigung erforderlich". Individual
 * grant status for accessibility, notifications, microphone and the rest is
 * deliberately not invented and not classified as required or optional until
 * the real Android state is bound.
 *
 * Compose mapping: PermissionsScreen(state, onBack), PermissionListItem.
 */

const permissionGroups = [
  {
    title: "Bedienungshilfen",
    purpose: "Generische App-Steuerung und Automation von Oberflächen.",
  },
  { title: "Benachrichtigungen", purpose: "Mitlesen und Beantworten von Benachrichtigungen." },
  { title: "Mikrofon", purpose: "Spracheingabe und lokale Spracherkennung." },
  { title: "Bildschirmzugriff", purpose: "Analyse sichtbarer Inhalte auf dem Bildschirm." },
  { title: "Kamera", purpose: "Bildaufnahme für Anfragen, die ein Bild benötigen." },
  { title: "Dateien", purpose: "Lesen und Ablegen lokaler Dateien, etwa Modelldateien." },
  { title: "Kontakte / Kommunikation", purpose: "Aktionen rund um Kontakte und Nachrichten." },
  { title: "Standort", purpose: "Ortsbezogene Aktionen und Kontext." },
];

const UNBOUND_STATUS = "Status nicht gebunden";

export function PermissionsScreen({ onBack }: SystemDetailProps) {
  return (
    <ScrollBody>
      <SectionEnter index={0}>
        <DetailHeader title="Berechtigungen" subtitle="Android-Zugriffe" onBack={onBack} />
      </SectionEnter>

      <SectionEnter index={1}>
        <SectionHeader>Gesamtzustand</SectionHeader>
        <ListGroup>
          <ListRow
            title="Android-Berechtigungen"
            subtitle="Der tatsächliche Systemzustand ist im Entwurfszustand noch nicht angebunden."
            trailing={
              <StatusTag
                state="permission_required"
                label={comparisonBaseline.labels.permissions}
              />
            }
          />
        </ListGroup>
      </SectionEnter>

      <SectionEnter index={2}>
        <SectionHeader>Zugriffsbereiche</SectionHeader>
        <ListGroup>
          {permissionGroups.map((group) => (
            <ListRow
              key={group.title}
              title={group.title}
              subtitle={group.purpose}
              trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
            />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Der tatsächliche Android-Berechtigungsstatus wird später direkt vom System gelesen.
        </p>
      </SectionEnter>

      <SectionEnter index={3}>
        <SectionHeader>Freigabe</SectionHeader>
        <div className="px-4">
          <InlineNotice tone="info">
            Die Freigabe erfolgt später über den jeweils passenden Android-Berechtigungsablauf.
            Ein Widerruf bleibt dort, wo Android das unterstützt, über die Systemeinstellungen
            möglich. Im Entwurfszustand gibt es hier keine Schaltfläche, die eine Freigabe
            auslösen könnte.
          </InlineNotice>
        </div>
      </SectionEnter>

      <SectionEnter index={4}>
        <DesignStateNote />
      </SectionEnter>
    </ScrollBody>
  );
}
