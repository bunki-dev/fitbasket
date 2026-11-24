import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE is "/<repo>/" for GitHub Pages; "/" when served by the FastAPI server.
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  worker: { format: "es" },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
