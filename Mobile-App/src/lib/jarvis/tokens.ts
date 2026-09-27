/**
 * J.A.R.V.I.S Mobile - Design System Tokens (locked, Phase 3).
 *
 * Single source of truth for the values that are not expressible as Tailwind
 * utilities alone (layout metrics, motion, z-index). Colour, radius and font
 * tokens live in src/styles.css under @theme and are mirrored here for the
 * design system reference page only.
 *
 * Every value maps 1:1 to a Kotlin object later:
 *   object JarvisTokens { object Spacing { val md = 12.dp } ... }
 */

/* ---------- Colour (mirror of styles.css, reference only) ---------- */

export const colorTokens = [
  { name: "bg-0", varName: "--j-bg-0", hex: "#13191e", use: "App-Hintergrund" },
  { name: "bg-1", varName: "--j-bg-1", hex: "#171e24", use: "Listenfläche" },
  { name: "surface-1", varName: "--j-surface-1", hex: "#1b232a", use: "Angehobene Fläche" },
  { name: "surface-2", varName: "--j-surface-2", hex: "#202a32", use: "Ausgewählt, gedrückt" },
  { name: "border", varName: "--j-border", hex: "#33404a", use: "Rahmen" },
  { name: "border-soft", varName: "--j-border-soft", hex: "#262f37", use: "Feine Trennlinie" },
  { name: "text-1", varName: "--j-text-1", hex: "#f7f8f8", use: "Primärtext" },
  { name: "text-2", varName: "--j-text-2", hex: "#c1c8ce", use: "Sekundärtext" },
  { name: "text-3", varName: "--j-text-3", hex: "#7e8993", use: "Meta, Labels" },
  { name: "blue", varName: "--j-blue", hex: "#34aafb", use: "Aktiv, Fokus, lokal" },
  { name: "blue-soft", varName: "--j-blue-soft", hex: "#2196e8", use: "Gedrückter Akzent" },
  { name: "blue-dim", varName: "--j-blue-dim", hex: "#17699d", use: "Auswahlfläche" },
  { name: "success", varName: "--j-success", hex: "#42c983", use: "Bereit" },
  { name: "warning", varName: "--j-warning", hex: "#e7b34a", use: "Berechtigung, degradiert" },
  { name: "error", varName: "--j-error", hex: "#e06464", use: "Fehler, destruktiv" },
  { name: "disabled", varName: "--j-disabled", hex: "#59636c", use: "Inaktiv" },
] as const;

/* ---------- Typography ---------- */

export const typeScale = [
  { name: "title", px: 15, lh: 20, weight: 500, use: "Bildschirmtitel" },
  { name: "body", px: 13, lh: 20, weight: 400, use: "Listentitel, Fließtext" },
  { name: "body-sm", px: 12, lh: 16, weight: 400, use: "Sekundärtext" },
  { name: "meta", px: 11, lh: 16, weight: 400, use: "Untertitel, Status" },
  { name: "label-system", px: 11, lh: 16, weight: 500, use: "Abschnittslabel, Versalien" },
  { name: "mono", px: 11, lh: 16, weight: 400, use: "Werte, Bezeichner" },
] as const;

/* ---------- Spacing, radii, borders ---------- */

export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
} as const;

export const radii = { xs: 4, sm: 6, md: 8, lg: 12 } as const;

export const borders = { hairline: 1 } as const;

/* ---------- Layout density and targets ---------- */

export const layout = {
  /** Android touch target floor. */
  touchTargetMin: 48,
  topBarHeight: 56,
  runtimeStripHeight: 28,
  bottomNavHeight: 56,
  rowPaddingX: 16,
  rowPaddingY: 10,
  iconSm: 16,
  iconMd: 18,
  iconLg: 22,
} as const;

/** Prototype-frame stand-ins for WindowInsets / env(safe-area-inset-*). */
export const safeArea = { top: 28, bottom: 24 } as const;

/* ---------- Elevation ---------- */

export const elevation = {
  /** Flat surfaces separate by hairline border, not by shadow. */
  flat: "none",
  /** Sheets and dialogs only. */
  raised: "0 -8px 24px -12px rgba(0,0,0,0.7)",
  overlay: "0 24px 60px -24px rgba(0,0,0,0.8)",
} as const;

/* ---------- Z-index layers ---------- */

export const zIndex = {
  base: 0,
  runtimeStrip: 10,
  bottomNav: 20,
  scrim: 30,
  sheet: 40,
  dialog: 50,
  toast: 60,
} as const;

/* ---------- Motion ---------- */

export const duration = {
  /** Press feedback, tag colour changes. */
  instant: 80,
  /** Small state and colour transitions. */
  fast: 120,
  /** Default screen and layout movement. */
  standard: 180,
  /** Emphasised state change, indicator travel. */
  deliberate: 240,
  /** Sheets and dialogs, maximum allowed. */
  sheet: 280,
} as const;

export const easing = {
  /** Movement within the screen. */
  standard: "cubic-bezier(0.2, 0, 0, 1)",
  /** Entering elements, decelerate. */
  enter: "cubic-bezier(0.05, 0.7, 0.1, 1)",
  /** Leaving elements, accelerate. */
  exit: "cubic-bezier(0.3, 0, 0.8, 0.15)",
  /** Emphasised state transition, used sparingly. */
  emphasized: "cubic-bezier(0.2, 0, 0, 1)",
} as const;

export type DurationToken = keyof typeof duration;
export type EasingToken = keyof typeof easing;

export const motionRules = [
  "Bewegung erklärt Hierarchie und Richtung, sie dekoriert nicht.",
  "Keine Dauerschleifen, kein Pulsieren, keine Partikel, kein HUD.",
  "Keine Animation darf einen Erfolg zeigen, bevor der Zustand bestätigt ist.",
  "Bei „Reduzierte Bewegung“ entfällt jede Verschiebung, Deckkraft bleibt.",
] as const;
