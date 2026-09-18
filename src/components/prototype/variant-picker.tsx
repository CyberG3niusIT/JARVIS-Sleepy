import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Harness chrome. Styles live in src/styles.css and are the prototype-skill
 * spec verbatim: deliberately not themed with the JARVIS design system.
 */
export function VariantPicker({
  names,
  current,
  onSelect,
}: {
  names: string[];
  current: number;
  onSelect: (i: number) => void;
}) {
  const pickerRef = useRef<HTMLElement | null>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const [highlight, setHighlight] = useState({ width: 0, x: 0 });

  const measure = useCallback(() => {
    const el = itemRefs.current[current];
    if (el) setHighlight({ width: el.offsetWidth, x: el.offsetLeft });
  }, [current]);

  useLayoutEffect(measure, [measure, names.length]);

  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  useEffect(() => {
    const id = requestAnimationFrame(() =>
      requestAnimationFrame(() => pickerRef.current?.setAttribute("data-ready", "")),
    );
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const num = parseInt(e.key, 10);
      if (num >= 1 && num <= names.length) onSelect(num - 1);
      else if (e.key === "ArrowRight") onSelect((current + 1) % names.length);
      else if (e.key === "ArrowLeft") onSelect((current - 1 + names.length) % names.length);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [current, names.length, onSelect]);

  return (
    <nav className="proto-picker" aria-label="Prototypvarianten" ref={pickerRef}>
      <span
        className="proto-picker-highlight"
        aria-hidden="true"
        style={{ width: highlight.width, transform: `translateX(${highlight.x}px)` }}
      />
      {names.map((name, i) => (
        <button
          key={name}
          type="button"
          className="proto-picker-item"
          ref={(el) => {
            itemRefs.current[i] = el;
          }}
          {...(i === current ? { "data-active": true, "aria-current": "true" as const } : {})}
          onClick={() => onSelect(i)}
        >
          {name}
        </button>
      ))}
    </nav>
  );
}
