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
  /**
   * Object URL for the local preview. It stays valid after sending, because the
   * sent message still shows it, and is revoked on explicit removal, on
   * conversation reset and when the screen unmounts.
   */
  previewUrl?: string;
}

/** Accepted input types. Office documents and audio are deliberately excluded. */
export const attachmentAccept = "image/*,.pdf,application/pdf";

export function classifyAttachment(file: File): ChatAttachmentKind | null {
  if (file.type.startsWith("image/")) return "image";
  if (file.type === "application/pdf") return "pdf";
  // Some providers hand over an empty or unreliable MIME type, for example
  // application/octet-stream, so fall back to the file ending. Nothing beyond
  // images and PDF is accepted, images still need a real image MIME type.
  if (file.name.toLowerCase().endsWith(".pdf")) return "pdf";
  return null;
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
