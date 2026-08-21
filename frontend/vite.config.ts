import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Local-only dev server; the backend it talks to is also loopback-bound.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8420",
        ws: true,
      },
    },
  },
});
