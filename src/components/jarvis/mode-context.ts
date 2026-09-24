import { createContext, useContext } from "react";

/**
 * True while the UI shows static prototype data, false when the ProductionAdapter feeds it.
 * Only used to pick honest wording; no data or state is derived from it.
 */
// Default false: a component outside the provider must not claim prototype data.
export const PrototypeModeContext = createContext(false);

export function usePrototype() {
  return useContext(PrototypeModeContext);
}
