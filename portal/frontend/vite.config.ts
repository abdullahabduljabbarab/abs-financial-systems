import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the BFF runs on :8080 and the app proxies /api to it. In
// production the BFF serves this build from the same origin, so /api is relative.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/healthz": "http://localhost:8080",
    },
  },
  build: {
    outDir: "dist",
  },
});
