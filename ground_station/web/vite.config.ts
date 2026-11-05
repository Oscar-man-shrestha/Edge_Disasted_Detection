/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const STATION = process.env.GS_DEV_STATION ?? "http://127.0.0.1:5000";
const proxied = ["/api", "/alert", "/snap", "/tiles", "/terrain", "/report", "/health"];

export default defineConfig({
  base: "/static/app/",
  plugins: [react(), tailwindcss()],
  worker: { format: "es" },
  build: {
    outDir: "../static/app",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/maplibre-gl")) return "maplibre";
          if (id.includes("node_modules/echarts") || id.includes("node_modules/zrender")) return "echarts";
          return undefined;
        },
      },
    },
  },
  server: { proxy: Object.fromEntries(proxied.map((p) => [p, { target: STATION, changeOrigin: false }])) },
  test: {
    environment: "jsdom",
    setupFiles: ["tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    css: false,
  },
});
