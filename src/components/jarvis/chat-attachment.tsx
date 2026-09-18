import { useEffect, useRef, useState } from "react";
import { X, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionEnter } from "@/components/jarvis/motion";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

/**
 * Chat attachment primitives.
 *
 * Only images and PDF files are supported in this pass. Nothing here uploads,
 * extracts or analyses anything: an attachment is carried with the message and
 * shown truthfully. No progress, no OCR claim, no automatic handoff.
 *
 * Compose mapping: ChatAttachmentChip, ChatAttachmentDraftRow, ChatAttachmentList.
 */

export type ChatAttachmentKind = "image" | "pdf";

export interface ChatAttachment {
  id: string;
  kind: ChatAttachmentKind;
  name: string;
  /** Size in bytes of the selected file, used for the local draft budget. */
  size: number;
  /**
   * Object URL for the local preview. It stays valid after sending, because the
   * sent message still shows it, and is revoked on explicit removal, on
   * conversation reset and when the screen unmounts.
   */
  previewUrl?: string;
}

/** Accepted input types. Office documents and audio are deliberately excluded. */
export const attachmentAccept = "image/*,.pdf,application/pdf";

/* ------------------------------ Local limits ------------------------------ */

export const MAX_ATTACHMENTS = 8;
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_TOTAL_BYTES = 50 * 1024 * 1024;

export function formatMiB(bytes: number): string {
  return `${Math.round((bytes / (1024 * 1024)) * 10) / 10} MiB`;
}

/* --------------------------- Content validation --------------------------- */

/**
 * Browser-side validation only. It reads the first header bytes and requires
 * extension, MIME type and magic bytes to agree, so a renamed or double
 * extension file such as "rechnung.pdf.exe" with a spoofed MIME type is
 * rejected before any object URL is created.
 *
 * IMPORTANT for a future backend: this check is a usability guard, never a
 * security boundary. Any server that later receives these files MUST validate
 * size and content signature again on the server side and must never trust the
 * browser supplied MIME type, file name or extension.
 */

interface SignatureRule {
  kind: ChatAttachmentKind;
  extensions: string[];
  mimeTypes: string[];
  /** Signature check against the first header bytes. */
  matches: (bytes: Uint8Array) => boolean;
}

function startsWith(bytes: Uint8Array, expected: number[], offset = 0): boolean {
  return expected.every((b, i) => bytes[offset + i] === b);
}

const ascii = (text: string) => Array.from(text, (ch) => ch.charCodeAt(0));

const signatureRules: SignatureRule[] = [
  {
    kind: "pdf",
    extensions: [".pdf"],
    // An unreliable or empty MIME type is tolerated only because the %PDF
    // signature is checked as well.
    mimeTypes: ["application/pdf", "application/octet-stream", ""],
    matches: (b) => startsWith(b, ascii("%PDF-")),
  },
  {
    kind: "image",
    extensions: [".png"],
    mimeTypes: ["image/png"],
    matches: (b) => startsWith(b, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  },
  {
    kind: "image",
    extensions: [".jpg", ".jpeg"],
    mimeTypes: ["image/jpeg"],
    matches: (b) => startsWith(b, [0xff, 0xd8, 0xff]),
  },
  {
    kind: "image",
    extensions: [".gif"],
    mimeTypes: ["image/gif"],
    matches: (b) => startsWith(b, ascii("GIF87a")) || startsWith(b, ascii("GIF89a")),
  },
  {
    kind: "image",
    extensions: [".webp"],
    mimeTypes: ["image/webp"],
    matches: (b) => startsWith(b, ascii("RIFF")) && startsWith(b, ascii("WEBP"), 8),
  },
];

export type AttachmentCheck =
  | { ok: true; kind: ChatAttachmentKind }
  | { ok: false; reason: string };

export async function validateAttachment(file: File): Promise<AttachmentCheck> {
  const name = file.name.toLowerCase();
  const rule = signatureRules.find((r) => r.extensions.some((ext) => name.endsWith(ext)));
  if (!rule) {
    return {
      ok: false,
      reason: "Dateityp wird nicht unterstützt. Erlaubt sind PNG, JPEG, GIF, WebP und PDF.",
    };
  }
  if (!rule.mimeTypes.includes(file.type)) {
    return {
      ok: false,
      reason: "Dateityp und Inhaltstyp passen nicht zusammen.",
    };
  }
  const header = new Uint8Array(await file.slice(0, 16).arrayBuffer());
  if (!rule.matches(header)) {
    return {
      ok: false,
      reason: "Dateiinhalt passt nicht zur Dateiendung.",
    };
  }
  return { ok: true, kind: rule.kind };
}

/** Exit duration of a removed draft row, matching the fast motion token. */
const REMOVE_EXIT_MS = 120;

export const attachmentKindLabel: Record<ChatAttachmentKind, string> = {
  image: "Bild",
  pdf: "PDF",
};

/* --------------------------- Draft (before send) --------------------------- */

export function AttachmentDraftList({
  attachments,
  onRemove,
}: {
  attachments: ChatAttachment[];
  onRemove: (id: string) => void;
}) {
  const reduced = useReducedMotion();
  const [exiting, setExiting] = useState<string[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const startRemove = (id: string) => {
    if (timers.current[id]) return;
    setExiting((prev) => [...prev, id]);
    timers.current[id] = setTimeout(() => {
      delete timers.current[id];
      setExiting((prev) => prev.filter((x) => x !== id));
      onRemove(id);
    }, REMOVE_EXIT_MS);
  };

  // Pending exit timers are dropped on unmount, without removing anything.
  const pending = timers.current;
  useEffect(
    () => () => {
      Object.values(pending).forEach(clearTimeout);
    },
    [pending],
  );

  if (attachments.length === 0) return null;
  return (
    <ul className="flex flex-col divide-y divide-border-soft border-b border-border-soft">
      {attachments.map((a) => {
        const leaving = exiting.includes(a.id);
        return (
          <li key={a.id} className={cn(leaving && (reduced ? "j-scrim-exit" : "j-row-exit"))}>
            <SectionEnter index={0}>
              <div className="flex items-center gap-3 px-3 py-2">
                <AttachmentThumb attachment={a} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] leading-4 text-foreground">
                    {a.name}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-4 text-muted-foreground">
                    {attachmentKindLabel[a.kind]}, angehängt
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => startRemove(a.id)}
                  disabled={leaving}
                  aria-label={`Anhang entfernen: ${a.name}`}
                  className="j-pressable flex size-12 shrink-0 items-center justify-center rounded-sm"
                >
                  <X className="size-4 text-muted-foreground" aria-hidden />
                </button>
              </div>
            </SectionEnter>
          </li>
        );
      })}
    </ul>
  );
}

/* ---------------------------- Sent (in message) ---------------------------- */

export function MessageAttachmentList({
  attachments,
  className,
}: {
  attachments: ChatAttachment[];
  className?: string;
}) {
  if (attachments.length === 0) return null;
  return (
    <ul className={cn("mt-2 flex flex-col gap-1.5", className)}>
      {attachments.map((a) => (
        <li key={a.id} className="flex items-center gap-2">
          <AttachmentThumb attachment={a} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12px] leading-4 text-foreground">
              {a.name}
            </span>
            <span className="block text-[11px] leading-4 text-muted-foreground">
              {attachmentKindLabel[a.kind]}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function AttachmentThumb({ attachment }: { attachment: ChatAttachment }) {
  if (attachment.kind === "image" && attachment.previewUrl) {
    return (
      <img
        src={attachment.previewUrl}
        alt={`Vorschau: ${attachment.name}`}
        className="size-9 shrink-0 rounded-xs border border-border-soft object-cover"
      />
    );
  }
  return (
    <span
      className="flex size-9 shrink-0 items-center justify-center rounded-xs border border-border-soft"
      aria-hidden
    >
      <FileText className="size-4 text-muted-foreground" />
    </span>
  );
}
