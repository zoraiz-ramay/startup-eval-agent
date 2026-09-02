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
  // The Vitest-only "browser" resolve condition (needed for @siemens/ix-react — see
  // vitest.config.js) deliberately does not live here: this file also drives `vite build`/`vite
  // dev`, and confirmed by diffing `npm run build` output with/without it, Vite's client build
  // already resolves the browser condition by default — adding it here would be a no-op for the
  // production bundle but would widen this config's blast radius to builds/dev for no reason.
});
