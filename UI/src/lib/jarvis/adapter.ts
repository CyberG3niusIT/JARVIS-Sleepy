import { isTauri } from "@tauri-apps/api/core";
import type { JarvisAdapter } from "./types";
import { prototypeAdapter } from "./prototype-adapter";
import { productionAdapter } from "./production-adapter";

/** The desktop executable always uses live data; browsers keep the explicit prototype default. */
export const jarvisAdapter: JarvisAdapter =
  isTauri() || import.meta.env["VITE_JARVIS_ADAPTER"] === "production"
    ? productionAdapter
    : prototypeAdapter;
