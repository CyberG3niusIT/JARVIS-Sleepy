import { useEffect, useRef, useState, type ReactNode } from "react";
import { Mic, Send } from "lucide-react";
import { cn } from "@/lib/utils";
import { ExecutionTag, StatusTag } from "@/components/jarvis/primitives";
import { SectionEnter, ValueTransition } from "@/components/jarvis/motion";
import { comparisonBaseline } from "@/lib/jarvis/comparison";
import type { ExecutionLocation } from "@/lib/jarvis/ia";

/**
 * Chat: conversational control surface of JARVIS Mobile (Phase 5, page 2).
 *
 * Every result carries its execution location. Nothing is generated here:
 * the prototype shows a clearly marked example conversation and truthful
 * design states. No model, no latency, no progress, no silent fallback.
 *
 * Compose mapping:
 *   ChatScreen(state: ChatUiState, onSend, onCancelTask)
 *   ChatMessageItem, ChatActionRow, ChatTaskState, ChatComposer
 */

/* ------------------------------ Model ------------------------------- */

/** Task lifecycle for a request. Reusable, only what is needed is rendered. */
export type ChatTaskStateId =
  | "RUNNING"
  | "WAITING_FOR_REMOTE"
  | "BLOCKED_BY_PRIVACY"
  | "PERMISSION_REQUIRED"
  | "ERROR";

export interface ChatActionItem {
  /** What the action does, in user language. */
  label: string;
  /** Confirmation requirement. Never a success claim before confirmation. */
  requirement: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "jarvis" | "system";
  text: string;
  /** Where the answer was produced. Only set when it is actually known. */
  execution?: ExecutionLocation;
  actions?: ChatActionItem[];
  task?: ChatTaskStateId;
}

/**
 * Prototype fixture, not persisted user history. It exists to demonstrate the
 * two required response patterns: deterministic local action and permission
 * required.
 */
const demoConversation: ChatMessage[] = [
  {
    id: "demo-1",
    role: "user",
    text: "Stell das Handy auf lautlos und wecke mich um 6:30.",
  },
  {
    id: "demo-2",
    role: "jarvis",
    text: "Zwei Android-Aktionen vorbereitet. Ausführung deterministisch, ohne Modell.",
    execution: "LOKAL",
    actions: [
      { label: "Lautlos aktivieren", requirement: "Bestätigung erforderlich" },
      { label: "Wecker 06:30 stellen", requirement: "Bestätigung erforderlich" },
    ],
  },
  {
    id: "demo-3",
    role: "user",
    text: "Fasse den sichtbaren Inhalt zusammen.",
  },
  {
    id: "demo-4",
    role: "jarvis",
    text: "Bildschirmanalyse benötigt die Android-Berechtigung für Bildschirmzugriff. Ohne Freigabe passiert nichts, kein stiller Fallback und keine automatische Übergabe.",
    task: "PERMISSION_REQUIRED",
  },
];

const examplePrompts = [
  "Öffne Spotify",
  "Stell einen Wecker auf 6:30",
  "Fasse den sichtbaren Inhalt zusammen",
];

/* ------------------------------ Screen ------------------------------- */

export function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>(demoConversation);
  /** Static part of the transcript. Everything after it is announced live. */
  const [baseCount, setBaseCount] = useState(demoConversation.length);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length]);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    const stamp = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: `u-${stamp}`, role: "user", text },
      {
        id: `s-${stamp}`,
        role: "system",
        text: `Keine Antwort erzeugt. ${comparisonBaseline.labels.runtime}, ${comparisonBaseline.labels.localModel}. Der Prototyp übernimmt die Eingabe nur als Entwurfszustand.`,
      },
    ]);
    setDraft("");
    inputRef.current?.focus();
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex min-h-full flex-col">
      <ChatHeader
        showReset={!isEmpty}
        onReset={() => {
          setMessages([]);
          setBaseCount(0);
          inputRef.current?.focus();
        }}
      />

      <div className="flex-1">
        {isEmpty ? (
          <EmptyConversation
            onPick={(prompt) => {
              setDraft(prompt);
              inputRef.current?.focus();
            }}
          />
        ) : (
          <ol className="flex flex-col gap-3 px-4 py-3 pb-0">
            {messages.slice(0, baseCount).map((m) => (
              <li key={m.id}>
                <SectionEnter index={0}>
                  <MessageItem message={m} />
                </SectionEnter>
              </li>
            ))}
          </ol>
        )}
        {/* Only newly appended turns are announced, the static example is not. */}
        <ol
          aria-live="polite"
          aria-relevant="additions"
          className="flex flex-col gap-3 px-4 pt-3"
        >
          {messages.slice(baseCount).map((m) => (
            <li key={m.id}>
              <SectionEnter index={0}>
                <MessageItem message={m} />
              </SectionEnter>
            </li>
          ))}
        </ol>
        <div ref={endRef} />
      </div>

      <ChatComposer
        ref={inputRef}
        value={draft}
        onChange={setDraft}
        onSend={send}
      />
    </div>
  );
}

/** Slim marker so the example conversation is never read as real history. */
function ChatHeader({ showReset, onReset }: { showReset: boolean; onReset: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-border-soft px-4 py-2">
      <span className="label-system">
        {showReset ? "Prototypbeispiel" : "Neue Unterhaltung"}
      </span>
      {showReset ? (
        <button
          type="button"
          onClick={onReset}
          className="j-pressable min-h-12 rounded-sm px-1 text-[12px] text-muted-foreground"
        >
          Neue Unterhaltung
        </button>
      ) : null}
    </div>
  );
}

/* --------------------------- Empty state ----------------------------- */

function EmptyConversation({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <SectionEnter index={0}>
      <div className="px-4 pt-8">
        <h1 className="text-[15px] leading-5 text-foreground">Was soll ich erledigen?</h1>
        <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
          Lokale Aktionen, Fragen oder Abläufe. Standardausführung:{" "}
          {comparisonBaseline.execution}.
        </p>
        <ul className="mt-4 divide-y divide-border-soft border-y border-border-soft">
          {examplePrompts.map((p) => (
            <li key={p}>
              <button
                type="button"
                onClick={() => onPick(p)}
                className="j-pressable touch-row flex w-full items-center py-2.5 text-left"
              >
                <span className="text-[13px] leading-5 text-subtle-foreground">{p}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
          Beispiele übernehmen nur den Text in die Eingabe. Benötigt eine Aktion eine
          Berechtigung, wird das als Zustand angezeigt.
        </p>
      </div>
    </SectionEnter>
  );
}

/* ----------------------------- Messages ------------------------------ */

function MessageItem({
  message,
  onCancelTask,
}: {
  message: ChatMessage;
  /** Required before a cancellable task state may render its control. */
  onCancelTask?: () => void;
}) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[78%] rounded-sm rounded-br-xs bg-surface-selected px-3 py-2">
        <p className="text-[13px] leading-5 text-foreground">{message.text}</p>
      </div>
    );
  }

  if (message.role === "system") {
    return (
      <div className="rounded-sm border border-dashed border-border px-3 py-2">
        <StatusTag state="design_state" />
        <p className="mt-1 text-[12px] leading-5 text-muted-foreground">{message.text}</p>
      </div>
    );
  }

  return (
    <div className="max-w-[88%] border-l-2 border-border pl-3">
      {message.execution ? (
        <ValueTransition value={message.execution} className="mb-1">
          <ExecutionTag where={message.execution} />
        </ValueTransition>
      ) : null}
      <p className="text-[13px] leading-5 text-subtle-foreground">{message.text}</p>
      {message.actions ? <ActionRows actions={message.actions} /> : null}
      {message.task === "RUNNING" || message.task === "WAITING_FOR_REMOTE" ? (
        onCancelTask ? <TaskState state={message.task} onCancel={onCancelTask} /> : null
      ) : message.task ? (
        <TaskState state={message.task} />
      ) : null}
    </div>
  );
}

/** Compact action rows. A row never reads as done before confirmation. */
function ActionRows({ actions }: { actions: ChatActionItem[] }) {
  return (
    <ul className="mt-2 divide-y divide-border-soft rounded-sm border border-border-soft">
      {actions.map((a) => (
        <li key={a.label} className="flex items-center justify-between gap-3 px-2.5 py-2">
          <span className="text-[12px] leading-4 text-foreground">{a.label}</span>
          <span className="shrink-0 text-[11px] leading-4 text-warning">{a.requirement}</span>
        </li>
      ))}
    </ul>
  );
}

/* --------------------------- Task states ----------------------------- */

/** States that can be stopped by the user. They always need a real callback. */
export type CancellableTaskStateId = "RUNNING" | "WAITING_FOR_REMOTE";

const taskCopy: Record<
  ChatTaskStateId,
  {
    label: string;
    note: string;
    tag: ReactNode;
    /** Only set when the execution location is actually known. */
    execution?: ExecutionLocation;
  }
> = {
  RUNNING: {
    label: "Läuft",
    note: "Aufgabe wird lokal ausgeführt. Kein Fortschrittswert verfügbar.",
    tag: <StatusTag state="local" label="Läuft" />,
    execution: "LOKAL",
  },
  WAITING_FOR_REMOTE: {
    label: "Wartet auf vertraute Runtime",
    note: `Übergabe an Sleepy: ${comparisonBaseline.labels.sleepyHandoff}. Aktuell: ${comparisonBaseline.labels.sleepy}.`,
    tag: <StatusTag state="waiting_remote" label="Wartet" />,
    execution: "SLEEPY",
  },
  BLOCKED_BY_PRIVACY: {
    label: "Durch Privacy blockiert",
    note: "Der aktive Privacy Mode verbietet diese Ausführung. Es gibt keinen stillen Fallback.",
    tag: <StatusTag state="privacy_blocked" />,
  },
  PERMISSION_REQUIRED: {
    label: "Berechtigung erforderlich",
    note: "Ohne Freigabe passiert nichts. Freigabe erfolgt unter System, Berechtigungen.",
    tag: <StatusTag state="permission_required" />,
  },
  ERROR: {
    label: "Fehlgeschlagen",
    note: "Die Aufgabe konnte nicht abgeschlossen werden.",
    tag: <StatusTag state="error" />,
  },
};

/**
 * Reusable in-conversation task state. Running shows an honest indeterminate
 * indicator and a cancel action, never a percentage.
 * Cancellable states require onCancel, so an enabled control always does work.
 */
export type TaskStateProps =
  | { state: CancellableTaskStateId; onCancel: () => void }
  | { state: Exclude<ChatTaskStateId, CancellableTaskStateId>; onCancel?: never };

export function TaskState({ state, onCancel }: TaskStateProps) {
  const copy = taskCopy[state];
  return (
    <div className="mt-2 rounded-sm border border-border-soft px-2.5 py-2">
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2">
          <ValueTransition value={state}>{copy.tag}</ValueTransition>
          {copy.execution ? <ExecutionTag where={copy.execution} /> : null}
        </span>
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="j-pressable min-h-12 rounded-sm px-1 text-[12px] text-muted-foreground"
          >
            Abbrechen
          </button>
        ) : null}
      </div>
      {state === "RUNNING" ? (
        <span className="j-indeterminate-track mt-2 block rounded-full" aria-hidden>
          <span />
        </span>
      ) : null}
      <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">{copy.note}</p>
    </div>
  );
}

/* ----------------------------- Composer ------------------------------ */

function ChatComposer({
  ref,
  value,
  onChange,
  onSend,
}: {
  ref: React.Ref<HTMLTextAreaElement>;
  value: string;
  onChange: (next: string) => void;
  onSend: () => void;
}) {
  const canSend = value.trim().length > 0;
  return (
    <div className="sticky bottom-0 flex items-end gap-2 border-t border-border-soft bg-surface px-3 py-2">
      <label htmlFor="jarvis-composer" className="sr-only">
        Nachricht an J.A.R.V.I.S
      </label>
      <textarea
        id="jarvis-composer"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder="Lokal fragen oder Aktion nennen"
        className="max-h-28 min-h-12 flex-1 resize-none rounded-sm border border-border bg-surface px-3 py-3 leading-5 text-foreground transition-[border-color,box-shadow] duration-[var(--j-duration-fast)] ease-[var(--j-ease-standard)] outline-none placeholder:text-muted-foreground focus:border-primary/70 focus:shadow-[inset_0_0_0_1px_var(--color-primary)] motion-reduce:transition-none"
      />
      <button
        type="button"
        disabled
        aria-label="Spracheingabe, noch nicht implementiert"
        title="Spracheingabe: noch nicht implementiert"
        className="flex size-12 shrink-0 items-center justify-center rounded-sm border border-border-soft text-disabled"
      >
        <Mic className="size-4" aria-hidden />
      </button>
      <button
        type="button"
        onClick={onSend}
        disabled={!canSend}
        aria-label="Senden"
        data-filled={canSend ? "true" : undefined}
        className={cn(
          "flex size-12 shrink-0 items-center justify-center rounded-sm border",
          canSend
            ? "j-pressable border-primary bg-primary text-primary-foreground"
            : "border-border-soft text-disabled",
        )}
      >
        <Send className="size-4" aria-hidden />
      </button>
    </div>
  );
}
