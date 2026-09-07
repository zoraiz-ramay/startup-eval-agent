import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config.js";

// Split from vite.config.js on purpose: resolve.conditions below only needs to affect the test
// runner, not `vite build`/`vite dev`. Vitest reads this file instead of vite.config.js once it
// exists, so everything vite.config.js provides (the react plugin, dev proxy, build options) is
// carried forward explicitly via mergeConfig rather than duplicated.
export default mergeConfig(
  viteConfig,
  defineConfig({
    resolve: {
      // @siemens/ix-react's package.json maps the plain "node" export condition to
      // dist/components.server.js — an SSR build whose createComponent
      // (@stencil/react-output-target/ssr) never wires props to the underlying custom element.
      // Vitest resolves under Node even with `environment: "jsdom"`, so without this it silently
      // loads the SSR build and every IxPill prop (variant, background, pillColor) is dropped on
      // the floor. Confirmed via a diffed `npm run build` that the production bundle is unaffected
      // either way, since Vite's client build already applies the "browser" condition there.
      conditions: ["browser"],
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setup.js",
      // E2E lives in ui/e2e and is driven by Playwright, which owns its own runner.
      include: ["src/**/*.test.{js,jsx}"],
      restoreMocks: true,
    },
  }),
);
