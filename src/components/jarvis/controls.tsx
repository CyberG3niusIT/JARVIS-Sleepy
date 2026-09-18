import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, Info, Inbox, Lock, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusTag } from "./primitives";
import type { SystemState } from "@/lib/jarvis/ia";

/**
 * Locked interactive primitives.
 * Compose mapping: JarvisButton, JarvisSwitch, JarvisTextField, JarvisDialog,
 * JarvisBottomSheet, JarvisNotice, JarvisStatePanel.
 */

/* ------------------------------ Buttons ------------------------------ */

type ButtonVariant = "primary" | "secondary" | "destructive";

const buttonVariant: Record<ButtonVariant, string> = {
  primary: "bg-primary border-primary text-primary-foreground",
  secondary: "bg-transparent border-border text-subtle-foreground",
  destructive: "bg-transparent border-destructive/60 text-destructive",
};

export function Button({
  children,
  variant = "secondary",
  full = false,
  disabled = false,
  onClick,
  className,
}: {
  children: ReactNode;
  variant?: ButtonVariant;
  full?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "j-pressable inline-flex min-h-12 items-center justify-center rounded-sm border px-4 text-[13px] leading-5",
        buttonVariant[variant],
        full && "w-full",
        disabled && "border-border-soft text-disabled",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------- Toggle ------------------------------ */

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="j-pressable flex min-h-12 min-w-12 items-center justify-center rounded-sm bg-transparent px-1"
    >
      <span
        className={cn(
          "relative flex h-5 w-9 items-center rounded-full border transition-colors duration-[var(--j-duration-fast)] ease-[var(--j-ease-standard)]",
          checked ? "border-primary/60 bg-primary/25" : "border-border bg-surface-raised",
        )}
      >
        <span
          className={cn(
            "absolute size-3.5 rounded-full transition-transform duration-[var(--j-duration-standard)] ease-[var(--j-ease-standard)] motion-reduce:transition-none",
            checked ? "translate-x-[18px] bg-primary" : "translate-x-[3px] bg-disabled",
          )}
          aria-hidden
        />
      </span>
    </button>
  );
}

/* ---------------------------- Text input ----------------------------- */

export function TextInput({
  value,
  onChange,
  placeholder,
  label,
  id,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  label: string;
  id: string;
}) {
  return (
    <div className="px-4">
      <label htmlFor={id} className="label-system block pb-1.5">
        {label}
      </label>
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-12 w-full rounded-sm border border-border bg-surface px-3 text-[13px] text-foreground transition-[border-color,box-shadow] duration-[var(--j-duration-fast)] ease-[var(--j-ease-standard)] outline-none placeholder:text-muted-foreground focus:border-primary/70 focus:shadow-[inset_0_0_0_1px_var(--color-primary)] motion-reduce:transition-none"
      />
    </div>
  );
}

/* ------------------------------ Overlays ----------------------------- */

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
}

export function Scrim({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label="Schließen"
      onClick={onClick}
      className="j-scrim-enter absolute inset-0 bg-black/55"
      style={{ zIndex: "var(--j-z-scrim)" }}
    />
  );
}

export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  useEscape(open, onClose);
  if (!open) return null;
  return (
    <>
      <Scrim onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="j-sheet-enter absolute inset-x-0 bottom-0 rounded-t-lg border-t border-border bg-surface-raised shadow-[var(--j-elevation-raised)]"
        style={{ zIndex: "var(--j-z-sheet)" }}
      >
        <div className="flex justify-center py-2" aria-hidden>
          <span className="h-1 w-9 rounded-full bg-border" />
        </div>
        <div className="flex items-center justify-between border-b border-border-soft px-4 pb-2">
          <h2 className="text-[13px] text-foreground">{title}</h2>
          <button
            type="button"
            aria-label="Schließen"
            onClick={onClose}
            className="j-pressable flex size-10 items-center justify-center rounded-sm"
          >
            <X className="size-4 text-muted-foreground" aria-hidden />
          </button>
        </div>
        <div className="pb-4">{children}</div>
      </div>
    </>
  );
}

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  useEscape(open, onClose);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);
  if (!open) return null;
  return (
    <>
      <Scrim onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center px-6" style={{ zIndex: "var(--j-z-dialog)" }}>
        <div
          ref={ref}
          tabIndex={-1}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="j-dialog-enter w-full rounded-md border border-border bg-surface-raised p-4 shadow-[var(--j-elevation-overlay)] outline-none"
        >
          <h2 className="text-[14px] text-foreground">{title}</h2>
          {description ? (
            <p className="mt-1.5 text-[12px] leading-5 text-muted-foreground">{description}</p>
          ) : null}
          <div className="mt-4 flex justify-end gap-2">{children}</div>
        </div>
      </div>
    </>
  );
}

/* ------------------------------- States ------------------------------ */

type NoticeTone = "info" | "warning" | "error";

const noticeTone: Record<NoticeTone, { ring: string; text: string; Icon: typeof Info }> = {
  info: { ring: "border-border", text: "text-subtle-foreground", Icon: Info },
  warning: { ring: "border-warning/50", text: "text-warning", Icon: AlertTriangle },
  error: { ring: "border-destructive/50", text: "text-destructive", Icon: AlertTriangle },
};

export function InlineNotice({
  tone = "info",
  children,
}: {
  tone?: NoticeTone;
  children: ReactNode;
}) {
  const { ring, text, Icon } = noticeTone[tone];
  return (
    <div className={cn("j-fade flex items-start gap-2.5 rounded-sm border px-3 py-2.5", ring)}>
      <Icon className={cn("mt-px size-4 shrink-0", text)} aria-hidden />
      <p className="text-[12px] leading-5 text-subtle-foreground">{children}</p>
    </div>
  );
}

/** Honest waiting indicator. Never shown for a state that is already known. */
export function LoadingState({ label = "Wird geladen" }: { label?: string }) {
  return (
    <div className="flex flex-col gap-2 px-4 py-4" role="status" aria-live="polite">
      <span className="text-[12px] text-muted-foreground">{label}</span>
      <span className="j-indeterminate-track rounded-full">
        <span />
      </span>
    </div>
  );
}

function StatePanel({
  icon,
  title,
  body,
  state,
  action,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  state?: SystemState;
  action?: ReactNode;
}) {
  return (
    <div className="j-fade flex flex-col items-start gap-2 rounded-sm border border-dashed border-border px-4 py-5">
      <span className="text-muted-foreground" aria-hidden>
        {icon}
      </span>
      <h3 className="text-[13px] text-foreground">{title}</h3>
      <p className="text-[12px] leading-5 text-muted-foreground">{body}</p>
      {state ? <StatusTag state={state} /> : null}
      {action}
    </div>
  );
}

export function EmptyState({
  title = "Noch nichts vorhanden",
  body = "Sobald Einträge entstehen, erscheinen sie hier.",
}: {
  title?: string;
  body?: string;
}) {
  return <StatePanel icon={<Inbox className="size-5" />} title={title} body={body} />;
}

export function ErrorState({
  title = "Vorgang fehlgeschlagen",
  body = "Der Vorgang konnte nicht abgeschlossen werden. Bitte erneut versuchen.",
  onRetry,
}: {
  title?: string;
  body?: string;
  onRetry?: () => void;
}) {
  return (
    <StatePanel
      icon={<AlertTriangle className="size-5 text-destructive" />}
      title={title}
      body={body}
      state="error"
      action={onRetry ? <Button onClick={onRetry}>Erneut versuchen</Button> : undefined}
    />
  );
}

export function PermissionRequiredState({
  title = "Berechtigung erforderlich",
  body = "Diese Fähigkeit braucht eine Android-Berechtigung. Ohne Freigabe passiert nichts, kein stiller Fallback.",
  onGrant,
}: {
  title?: string;
  body?: string;
  onGrant?: () => void;
}) {
  return (
    <StatePanel
      icon={<Lock className="size-5 text-warning" />}
      title={title}
      body={body}
      state="permission_required"
      action={onGrant ? <Button onClick={onGrant}>Berechtigung öffnen</Button> : undefined}
    />
  );
}

export function NotImplementedState({
  title = "Noch nicht implementiert",
  body = "Diese Fähigkeit ist geplant, aber im Prototyp nicht angebunden.",
}: {
  title?: string;
  body?: string;
}) {
  return (
    <StatePanel icon={<Info className="size-5" />} title={title} body={body} state="not_implemented" />
  );
}
