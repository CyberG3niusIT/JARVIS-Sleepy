import { invoke as tauriInvoke, isTauri } from "@tauri-apps/api/core";

/**
 * BackendDataTransport: HTTP/API data from the JARVIS backend (`jarvis_web.py`, llama-server,
 * Chatterbox, FLUX, VVS). Runtime state and lifecycle are a separate contract with a separate
 * transport (`runtime-control.ts`, RuntimeControlTransport) and never travel through this one.
 *
 * The adapter only depends on `BackendDataTransport`. The default implementation below is a plain
 * same-origin `fetch` against `/jarvis-api/<target>/...`. A later native bridge (Tauri command,
 * Electron main process, server function) implements the same interface and is installed with
 * `setBackendDataTransport()`; adapter and UI stay unchanged.
 *
 * Why same-origin: the backend (`jarvis_web.py`, llama-server, Chatterbox, FLUX) sends no CORS
 * headers, so a browser cannot read cross-origin responses. In dev/preview `vite.config.ts` forwards
 * `/jarvis-api/*` to the loopback services. That proxy is a development aid only; it does not exist
 * in a production build. Secrets (auth tokens) never live in this file or in any React code: the
 * forwarding side adds them. This layer performs no authentication of its own and does not try to
 * get around any access control of a service.
 */
export type JarvisTarget = "web" | "llm-main" | "llm-small" | "tts" | "flux" | "vvs";

export type TransportErrorKind =
  "unreachable" | "timeout" | "http" | "invalid-json" | "no-transport";

export class TransportError extends Error {
  readonly kind: TransportErrorKind;
  readonly status: number | undefined;
  constructor(kind: TransportErrorKind, message: string, status?: number) {
    super(message);
    this.name = "TransportError";
    this.kind = kind;
    this.status = status;
  }
}

export interface TransportOptions {
  timeoutMs?: number;
  signal?: AbortSignal;
}

export interface BackendDataTransport {
  /** GET `path` on `target` and return the parsed JSON body. Rejects with TransportError. */
  getJson<T>(target: JarvisTarget, path: string, options?: TransportOptions): Promise<T>;
}

const configuredBase = import.meta.env["VITE_JARVIS_API_BASE"] as string | undefined;
const customBase = Boolean(configuredBase && configuredBase.length > 0);
const apiBase = (
  configuredBase && configuredBase.length > 0 ? configuredBase : "/jarvis-api"
).replace(/\/+$/, "");

export const fetchTransport: BackendDataTransport = {
  async getJson<T>(target: JarvisTarget, path: string, options: TransportOptions = {}) {
    if (options.signal?.aborted)
      throw new TransportError("unreachable", `${target}${path}: abgebrochen`);
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs ?? 4000;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onAbort = () => controller.abort();
    options.signal?.addEventListener("abort", onAbort);
    try {
      let response: Response;
      try {
        response = await fetch(`${apiBase}/${target}${path}`, {
          signal: controller.signal,
          headers: { Accept: "application/json" },
        });
      } catch (error) {
        if (timedOut) throw new TransportError("timeout", `${target}${path}: Zeitüberschreitung`);
        if (options.signal?.aborted) throw error;
        throw new TransportError("unreachable", `${target}${path}: nicht erreichbar`);
      }
      // Without the dev proxy (production build) `/jarvis-api/*` is answered by the app host itself.
      // Anything not forwarded by our proxy must not be read as "the service answered".
      if (!customBase && response.headers.get("x-jarvis-proxy") === null)
        throw new TransportError("no-transport", `${target}${path}: kein Transport verfügbar`);
      // The dev proxy answers itself (marked header) when the loopback service is down.
      if (response.headers.get("x-jarvis-proxy-error") !== null)
        throw new TransportError(
          "unreachable",
          `${target}${path}: nicht erreichbar`,
          response.status,
        );
      if (!response.ok)
        throw new TransportError(
          "http",
          `${target}${path}: HTTP ${response.status}`,
          response.status,
        );
      try {
        return (await response.json()) as T;
      } catch {
        throw new TransportError("invalid-json", `${target}${path}: ungültige Antwort`);
      }
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", onAbort);
    }
  },
};

/** Native requests use fixed service IDs and paths; the Rust side enforces the service allowlist. */
export const tauriBackendTransport: BackendDataTransport = {
  async getJson<T>(target: JarvisTarget, path: string, options: TransportOptions = {}) {
    if (!isTauri()) throw new TransportError("no-transport", "Tauri-Bridge nicht verfügbar");
    if (options.signal?.aborted)
      throw new TransportError("unreachable", `${target}${path}: abgebrochen`);
    try {
      return await tauriInvoke<T>("backend_get_json", {
        target,
        path,
        timeoutMs: options.timeoutMs ?? 4000,
      });
    } catch (error) {
      const message =
        typeof error === "string" ? error : error instanceof Error ? error.message : "";
      const statusMatch = message.match(/HTTP\s+(\d{3})/i);
      if (statusMatch) {
        const status = Number(statusMatch[1]);
        throw new TransportError("http", `${target}${path}: HTTP ${status}`, status);
      }
      if (/gültiges JSON/i.test(message))
        throw new TransportError("invalid-json", `${target}${path}: ungültige Antwort`);
      if (/Zeitüberschreitung/i.test(message))
        throw new TransportError("timeout", `${target}${path}: Zeitüberschreitung`);
      throw new TransportError("unreachable", `${target}${path}: native Anfrage fehlgeschlagen`);
    }
  },
};

let activeTransport: BackendDataTransport = fetchTransport;

export function setBackendDataTransport(transport: BackendDataTransport) {
  activeTransport = transport;
}

export function getJson<T>(target: JarvisTarget, path: string, options?: TransportOptions) {
  // This is evaluated lazily because Tauri can install its bridge after module evaluation.
  if (activeTransport === fetchTransport && isTauri()) activeTransport = tauriBackendTransport;
  return activeTransport.getJson<T>(target, path, options);
}
