import type { JarvisAdapter } from "./types";
import { prototypeAdapter } from "./prototype-adapter";
import { productionAdapter } from "./production-adapter";

/** Prototype is the default; set VITE_JARVIS_ADAPTER=production to talk to the real backend. */
export const jarvisAdapter: JarvisAdapter =
  import.meta.env["VITE_JARVIS_ADAPTER"] === "production" ? productionAdapter : prototypeAdapter;
