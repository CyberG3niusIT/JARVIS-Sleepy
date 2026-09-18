import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import tsConfigPaths from "vite-tsconfig-paths";
import viteReact from "@vitejs/plugin-react";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";

/**
 * Project owned build configuration for J.A.R.V.I.S Mobile.
 *
 * Upstream packages only:
 *   vite, @vitejs/plugin-react, @tailwindcss/vite, vite-tsconfig-paths,
 *   @tanstack/react-start (TanStack Start plugin, which drives route
 *   generation through @tanstack/router-plugin) and nitro for the
 *   production server bundle.
 */
export default defineConfig(async ({ command }) => {
  const plugins = [
    tsConfigPaths({ projects: ["./tsconfig.json"] }),
    tailwindcss(),
    tanstackStart({
      // src/server.ts is the custom server entry (SSR wrapper and headers).
      server: { entry: "server" },
      importProtection: {
        behavior: "error",
        client: {
          files: ["**/server/**"],
          specifiers: ["server-only"],
        },
      },
    }),
  ];

  if (command === "build") {
    const { nitro } = await import("nitro/vite");
    plugins.push(nitro({ preset: process.env["NITRO_PRESET"] || "node-server" }));
  }

  plugins.push(viteReact());

  return {
    plugins,
    server: {
      host: true,
      port: 8080,
      strictPort: true,
      allowedHosts: true as const,
    },
    preview: {
      host: true,
      port: 8080,
      strictPort: true,
    },
    resolve: {
      dedupe: ["react", "react-dom"],
    },
  };
});
