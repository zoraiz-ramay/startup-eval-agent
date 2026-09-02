import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend so no CORS is needed in dev
// and the browser never talks to the backend origin directly.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
      "/health": { target: process.env.VITE_API_PROXY || "http://localhost:8000", changeOrigin: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
  // @siemens/ix-react's package.json maps the plain "node" export condition to
  // dist/components.server.js — an SSR build whose createComponent (@stencil/react-output-target/ssr)
  // never wires props to the underlying custom element. Vitest still runs under Node even with
  // `environment: "jsdom"`, so without forcing the browser condition it silently loads the SSR
  // build and every IxPill prop (variant, background, pillColor) is dropped on the floor.
  resolve: { conditions: ["browser"] },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.js",
    // E2E lives in ui/e2e and is driven by Playwright, which owns its own runner.
    include: ["src/**/*.test.{js,jsx}"],
    restoreMocks: true,
  },
});
