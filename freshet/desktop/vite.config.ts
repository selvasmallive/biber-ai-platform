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
  // Tauri drives this dev server, so the port must be fixed and failures must
  // be loud rather than silently landing on another port.
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    target: "es2021",
    sourcemap: false,
  },
});
