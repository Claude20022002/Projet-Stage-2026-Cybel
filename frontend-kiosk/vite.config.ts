import { defineConfig } from "vite";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/kiosk/" : "/",
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
