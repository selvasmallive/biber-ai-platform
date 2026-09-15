import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    // Transmission and entitlement live on the licence service. Everything
    // else — the whole calculation — happens in the page and never reaches it.
    proxy: {
      "/api": { target: "http://127.0.0.1:8080", changeOrigin: true },
    },
  },
  build: {
    target: "es2022",
    sourcemap: false,
  },
});
