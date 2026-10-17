import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  // The shared components in ../shared are outside this app's tree, so the
  // bundler resolves their `react` import from there and finds nothing. Point
  // it at ours. Aliasing rather than hoisting a workspace keeps the two apps
  // independently installable.
  resolve: {
    alias: {
      react: fileURLToPath(new URL("./node_modules/react", import.meta.url)),
      "react/jsx-runtime": fileURLToPath(
        new URL("./node_modules/react/jsx-runtime", import.meta.url),
      ),
      "react-dom": fileURLToPath(
        new URL("./node_modules/react-dom", import.meta.url),
      ),
    },
  },
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
