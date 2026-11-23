/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? "/",
  server: { port: 5174, proxy: { "/api": { target: "http://127.0.0.1:8100", changeOrigin: true } } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
});
