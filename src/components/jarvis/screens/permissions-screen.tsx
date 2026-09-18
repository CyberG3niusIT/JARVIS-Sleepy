import { useState } from "react";
import { ScrollBody } from "@/components/prototype/phone-frame";
import { ListGroup, ListRow, SectionHeader, StatusTag } from "@/components/jarvis/primitives";
import { SectionEnter } from "@/components/jarvis/motion";
import { BottomSheet, Button, InlineNotice } from "@/components/jarvis/controls";
import {
  DesignStateNote,
  DetailHeader,
  type SystemDetailProps,
} from "@/components/jarvis/screens/detail-header";
import { ActionResult, DEMO_AREA_NOTE, DESIGN_STATE_ACTION, DetailField, useActionResult } from "@/components/jarvis/prototype-state";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Berechtigungen: Android access as capabilities, not onboarding checkboxes.
 *
 * The baseline only knows the generic "Berechtigung erforderlich". Individual
 * grant status for accessibility, notifications, microphone and the rest is
 * deliberately not invented and not classified as required or optional until
 * the real Android state is bound. Each category opens a detail sheet that
 * explains why the access exists and what it unlocks; the only interactive
 * state changes live in a clearly labelled demonstration area inside that
 * sheet, never in the baseline list itself.
 *
 * Compose mapping: PermissionsScreen(state, onBack), PermissionListItem,
 * PermissionDetailSheet.
 */

/** Grant-state machine for a single permission category. Demo-local only. */
export type PermissionGrantState =
  | "not_requested"
  | "granted"
  | "denied"
  | "denied_permanently"
  | "revoked"
  | "not_applicable";

export const permissionGrantLabel: Record<PermissionGrantState, string> = {
  not_requested: "Nicht angefragt",
  granted: "Erteilt",
  denied: "Abgelehnt",
  denied_permanently: "Dauerhaft abgelehnt",
  revoked: "Widerrufen",
  not_applicable: "Nicht zutreffend",
};

const permissionGrantTone: Record<PermissionGrantState, SystemState> = {
  not_requested: "design_state",
  granted: "ready",
  denied: "permission_required",
  denied_permanently: "error",
  revoked: "offline",
  not_applicable: "design_state",
};

type Requirement = "Erforderlich" | "Optional" | "Nicht festgelegt";

interface PermissionGroup {
  id: string;
  title: string;
  purpose: string;
  whyNeeded: string;
  capabilities: string[];
  requirement: Requirement;
}

const permissionGroups: PermissionGroup[] = [
  {
    id: "accessibility",
    title: "Bedienungshilfen",
    purpose: "Generische App-Steuerung und Automation von Oberflächen.",
    whyNeeded:
      "Ermöglicht das Lesen und Bedienen sichtbarer Oberflächenelemente in anderen Apps, damit Aktionen im Namen der Nutzerin oder des Nutzers ausgeführt werden können.",
    capabilities: [
      "Oberflächenelemente in anderen Apps erkennen",
      "Tippen, Wischen und Texteingabe auslösen",
      "Automatisierte Bedienabläufe ausführen",
    ],
    requirement: "Nicht festgelegt",
  },
  {
    id: "notifications",
    title: "Benachrichtigungen",
    purpose: "Mitlesen und Beantworten von Benachrichtigungen.",
    whyNeeded:
      "Erlaubt das Erfassen eingehender Benachrichtigungen und das Auslösen passender Antworten oder Aktionen.",
    capabilities: [
      "Benachrichtigungsinhalte lesen",
      "Schnellantworten aus Benachrichtigungen senden",
      "Benachrichtigungen wegwischen oder öffnen",
    ],
    requirement: "Nicht festgelegt",
  },
  {
    id: "microphone",
    title: "Mikrofon",
    purpose: "Spracheingabe und lokale Spracherkennung.",
    whyNeeded: "Wird für gesprochene Anfragen und lokale Spracherkennung benötigt.",
    capabilities: ["Audio für Spracherkennung aufnehmen", "Sprachbefehle entgegennehmen"],
    requirement: "Nicht festgelegt",
  },
  {
    id: "screen",
    title: "Bildschirmzugriff",
    purpose: "Analyse sichtbarer Inhalte auf dem Bildschirm.",
    whyNeeded: "Wird benötigt, um Anfragen zu beantworten, die sich auf den aktuell sichtbaren Bildschirminhalt beziehen.",
    capabilities: ["Sichtbaren Bildschirminhalt auswerten", "Bildschirmkontext für Anfragen bereitstellen"],
    requirement: "Nicht festgelegt",
  },
  {
    id: "camera",
    title: "Kamera",
    purpose: "Bildaufnahme für Anfragen, die ein Bild benötigen.",
    whyNeeded: "Wird für Anfragen benötigt, die ein aktuelles Kamerabild als Grundlage brauchen.",
    capabilities: ["Einzelbild aufnehmen", "Aufgenommenes Bild einer Anfrage zuordnen"],
    requirement: "Nicht festgelegt",
  },
  {
    id: "files",
    title: "Dateien",
    purpose: "Lesen und Ablegen lokaler Dateien, etwa Modelldateien.",
    whyNeeded: "Wird benötigt, um lokale Dateien wie Modelldateien zu lesen und abzulegen.",
    capabilities: ["Lokale Dateien lesen", "Dateien im freigegebenen Bereich ablegen"],
    requirement: "Nicht festgelegt",
  },
  {
    id: "contacts",
    title: "Kontakte / Kommunikation",
    purpose: "Aktionen rund um Kontakte und Nachrichten.",
    whyNeeded: "Wird für Aktionen benötigt, die einen Kontakt nachschlagen oder eine Nachricht auslösen.",
    capabilities: ["Kontakte nachschlagen", "Nachrichten über freigegebene Kanäle auslösen"],
    requirement: "Nicht festgelegt",
  },
  {
    id: "location",
    title: "Standort",
    purpose: "Ortsbezogene Aktionen und Kontext.",
    whyNeeded: "Wird für Anfragen benötigt, die einen aktuellen oder ungefähren Standort als Kontext brauchen.",
    capabilities: ["Aktuellen Standort als Kontext bereitstellen", "Ortsbezogene Aktionen ermöglichen"],
    requirement: "Nicht festgelegt",
  },
];

const UNBOUND_STATUS = "Status nicht gebunden";

export function PermissionsScreen({ onBack }: SystemDetailProps) {
  const [openId, setOpenId] = useState<string | null>(null);
  const openGroup = permissionGroups.find((g) => g.id === openId) ?? null;

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
              key={group.id}
              title={group.title}
              subtitle={group.purpose}
              trailing={<StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />}
              chevron
              onClick={() => setOpenId(group.id)}
            />
          ))}
        </ListGroup>
        <p className="px-4 pt-2 text-[11px] leading-4 text-muted-foreground">
          Der tatsächliche Android-Berechtigungsstatus wird später direkt vom System gelesen.
          Details je Zugriffsbereich öffnen die jeweilige Detailansicht.
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

      <PermissionDetailSheet
        group={openGroup}
        onClose={() => setOpenId(null)}
      />
    </ScrollBody>
  );
}

/* ---------------------------- Permission detail --------------------------- */

function PermissionDetailSheet({
  group,
  onClose,
}: {
  group: PermissionGroup | null;
  onClose: () => void;
}) {
  const [demoState, setDemoState] = useState<PermissionGrantState>("not_requested");
  const { message, report } = useActionResult();

  const requestPermission = () => {
    setDemoState((prev) =>
      prev === "not_requested" || prev === "revoked" || prev === "denied" ? "granted" : prev,
    );
    report(`Demo-Zustand auf "Erteilt" gesetzt. ${DESIGN_STATE_ACTION}`);
  };

  const openAndroidSettings = () => {
    report(
      `Android-Einstellungen wurden nicht geöffnet, es besteht keine Systemanbindung. ${DESIGN_STATE_ACTION}`,
    );
  };

  const resetDemo = () => {
    setDemoState("not_requested");
    report(`Demo-Zustand zurückgesetzt. ${DESIGN_STATE_ACTION}`);
  };

  return (
    <BottomSheet
      open={group !== null}
      onClose={onClose}
      title={group ? group.title : "Berechtigung"}
    >
      {group ? (
        <div className="flex flex-col">
          <DetailField label="Warum nötig">{group.whyNeeded}</DetailField>
          <DetailField label="Freigeschaltete Fähigkeiten">
            <span className="flex flex-col items-end gap-0.5">
              {group.capabilities.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </span>
          </DetailField>
          <DetailField label="Erforderlichkeit">{group.requirement}</DetailField>
          <DetailField label="Aktueller Zustand">
            <StatusTag state="design_state" label={UNBOUND_STATUS} dot={false} />
          </DetailField>

          <div className="px-4 pt-4">
            <SectionHeader className="px-0 pt-0">Zustandsdemonstration</SectionHeader>
            <InlineNotice tone="info">{DEMO_AREA_NOTE}</InlineNotice>
          </div>

          <DetailField label="Demo-Zustand">
            <StatusTag state={permissionGrantTone[demoState]} label={permissionGrantLabel[demoState]} dot={false} />
          </DetailField>

          <p className="px-4 pt-1 text-[11px] leading-4 text-muted-foreground">
            Zustandsmuster: Nicht angefragt, Erteilt, Abgelehnt, Dauerhaft abgelehnt, Widerrufen,
            Nicht zutreffend.
          </p>

          <div className="flex flex-col gap-2 px-4 pt-3">
            <Button variant="primary" full onClick={requestPermission}>
              Berechtigung anfragen (Demo)
            </Button>
            <Button full onClick={openAndroidSettings}>
              Android-Einstellungen öffnen (Demo)
            </Button>
            <Button full onClick={resetDemo}>
              Demo-Zustand zurücksetzen
            </Button>
          </div>

          <ActionResult message={message} />
        </div>
      ) : null}
    </BottomSheet>
  );
}
