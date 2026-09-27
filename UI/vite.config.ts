// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import type { Plugin, ProxyOptions } from "vite";

// Same-origin forwarding to the real loopback services (dev/preview only). The backend sends no
// CORS headers, so the browser can only read responses that arrive from its own origin. The web
// token stays server-side: set JARVIS_WEB_AUTH_TOKEN in the shell that starts `npm run dev`.
// Hosts/ports come from the backend code (jarvis_web.py 8091, llama-server 8080/8081,
// chatterbox_server 8765, flux_server 8190) and can be overridden per environment variable.
const target = (envName: string, fallback: string) => process.env[envName] ?? fallback;
const authToken = process.env["JARVIS_WEB_AUTH_TOKEN"];
const webUrl = target("JARVIS_WEB_URL", "http://127.0.0.1:8091");

// The token is only ever sent to a target that has just been positively identified as
// jarvis_web.py: loopback host AND an unauthenticated GET /api/stats (redirects not followed) that
// answers with jarvis_web.py's own auth rejection (HTTP 401, body "Invalid or missing auth token",
// jarvis_web.py auth_middleware). The check runs in a middleware BEFORE each proxied request
// (result cached for ~1 s), so a target that changes (e.g. jarvis_web stops and the VVS API keeps
// port 8088) loses the token within a second. Anything unidentified, dead, non-loopback or
// redirecting never receives it. Residual risk: a local process that spoofs jarvis_web's 401 text
// on the configured loopback port; such a process can read the environment anyway.
const isLoopback = (url: string) => {
  try {
    return ["127.0.0.1", "localhost", "[::1]"].includes(new URL(url).hostname);
  } catch {
    return false;
  }
};
const localHost = (value: string | undefined) => {
  if (!value) return false;
  try {
    return ["127.0.0.1", "localhost", "[::1]"].includes(new URL(`http://${value}`).hostname);
  } catch {
    return false;
  }
};
let identifyCache: { at: number; result: Promise<boolean> } | undefined;
function identifyWeb(): Promise<boolean> {
  if (!authToken || !isLoopback(webUrl)) return Promise.resolve(false);
  if (identifyCache && Date.now() - identifyCache.at < 1000) return identifyCache.result;
  const result = (async () => {
    try {
      const response = await fetch(new URL("/api/stats", webUrl), {
        redirect: "manual",
        signal: AbortSignal.timeout(2000),
      });
      return (
        response.status === 401 && (await response.text()).includes("Invalid or missing auth token")
      );
    } catch {
      return false;
    }
  })();
  identifyCache = { at: Date.now(), result };
  return result;
}
const identifiedRequests = new WeakSet<object>();

// Dev/preview middleware in front of the proxy: refuses non-local Host/Origin (DNS rebinding) and
// marks requests to the web target whose destination was identified just now.
const jarvisGuard = (server: {
  middlewares: {
    use: (
      path: string,
      handler: (
        req: import("node:http").IncomingMessage,
        res: import("node:http").ServerResponse,
        next: () => void,
      ) => void,
    ) => void;
  };
}) => {
  server.middlewares.use("/jarvis-api", (req, res, next) => {
    const origin = req.headers.origin;
    const originHost = origin ? origin.replace(/^[a-z]+:\/\//i, "") : undefined;
    if (!localHost(req.headers.host) || (originHost !== undefined && !localHost(originHost))) {
      res.writeHead(403, { "content-type": "text/plain" });
      res.end("forbidden");
      return;
    }
    if ((req.url ?? "").startsWith("/web")) {
      void identifyWeb().then((identified) => {
        if (identified) identifiedRequests.add(req);
        next();
      });
      return;
    }
    next();
  });
};
const jarvisGuardPlugin: Plugin = {
  name: "jarvis-guard",
  configureServer: jarvisGuard,
  configurePreviewServer: jarvisGuard,
};

const service = (prefix: string, url: string, withAuth = false): ProxyOptions => ({
  target: url,
  changeOrigin: false,
  rewrite: (path) => path.slice(`/jarvis-api/${prefix}`.length) || "/",
  configure: (proxyServer) => {
    // Marks answers that really came through this proxy (see transport.ts).
    proxyServer.on("proxyRes", (proxyRes) => {
      proxyRes.headers["x-jarvis-proxy"] = "1";
    });
    proxyServer.on("proxyReq", (proxyReq, req) => {
      if (withAuth && authToken && identifiedRequests.has(req))
        proxyReq.setHeader("Authorization", `Bearer ${authToken}`);
    });
    proxyServer.on("error", (_error, _req, res) => {
      // `res` is a ServerResponse for HTTP requests (a Socket for WebSocket upgrades).
      if ("writeHead" in res && !res.headersSent) {
        // 200 + marker header instead of 502: a down loopback service is an expected state, not a
        // page error. transport.ts turns the marker into an "unreachable" TransportError.
        res.writeHead(200, { "x-jarvis-proxy": "1", "x-jarvis-proxy-error": "1" });
        res.end();
      }
    });
  },
});
const proxy = {
  "^/jarvis-api/web(/|$)": service("web", webUrl, true),
  "^/jarvis-api/llm-main(/|$)": service(
    "llm-main",
    target("JARVIS_LLM_MAIN_URL", "http://127.0.0.1:8080"),
  ),
  "^/jarvis-api/llm-small(/|$)": service(
    "llm-small",
    target("JARVIS_LLM_SMALL_URL", "http://127.0.0.1:8081"),
  ),
  "^/jarvis-api/tts(/|$)": service("tts", target("JARVIS_TTS_URL", "http://127.0.0.1:8765")),
  "^/jarvis-api/flux(/|$)": service("flux", target("JARVIS_FLUX_URL", "http://127.0.0.1:8190")),
  "^/jarvis-api/vvs(/|$)": service("vvs", target("JARVIS_VVS_URL", "http://127.0.0.1:8088")),
};

export default defineConfig({
  vite: {
    plugins: [jarvisGuardPlugin],
    server: { proxy },
    preview: { proxy },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
    // Tauri loads frontendDist as static files and requires index.html. Build a client-only shell
    // for the native executable; the real API/runtime state is loaded by the React app on start.
    spa: {
      enabled: true,
      maskPath: "/",
      prerender: {
        enabled: true,
        outputPath: "/index.html",
        crawlLinks: false,
        retryCount: 0,
      },
    },
  },
});
