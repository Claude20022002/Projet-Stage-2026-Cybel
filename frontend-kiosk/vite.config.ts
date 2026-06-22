import { defineConfig, type Plugin } from "vite";

/** Retire type="module" — incompatible WebView Android 7.1 */
function stripModuleType(): Plugin {
  return {
    name: "strip-module-type",
    transformIndexHtml(html) {
      return html
        .replace(/\s*type="module"\s*/g, " ")
        .replace(/\s*crossorigin\s*/g, " ");
    },
  };
}

/**
 * WebView Android 7.1 (Chrome ~51) : un seul bundle IIFE, sans ES modules.
 */
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/kiosk/" : "/",
  plugins: [stripModuleType()],
  build: {
    target: "chrome49",
    cssTarget: "chrome49",
    modulePreload: false,
    rollupOptions: {
      output: {
        format: "iife",
        entryFileNames: "assets/app.js",
        assetFileNames: "assets/[name][extname]",
        inlineDynamicImports: true,
      },
    },
  },
  server: {
    port: 5174,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
}));
