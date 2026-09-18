import { useEffect, useState } from "react";

/**
 * True when the platform asks for reduced motion.
 * Starts false on the server and on first paint, so SSR markup stays stable.
 * Maps later to Compose: LocalAccessibilityManager / Settings.Global animator scale.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return reduced;
}
