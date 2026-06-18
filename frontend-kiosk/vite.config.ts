import legacy from "@vitejs/plugin-legacy";
import { defineConfig } from "vite";

/** WebView Android 7.x (Chrome ~51) : pas de ES modules ni syntaxe récente. */
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/kiosk/" : "/",
  build: {
    target: "es2015",
    modulePreload: false,
  },
  plugins: [
    legacy({
      targets: ["chrome >= 49", "android >= 7"],
      renderModernChunks: false,
    }),
  ],
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
