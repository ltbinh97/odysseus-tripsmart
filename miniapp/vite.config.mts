import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The TripSmart backend (FastAPI) exposes POST /chat but sets NO CORS headers.
// We are NOT allowed to modify the backend, so in local browser dev we avoid
// CORS entirely by proxying:  /api/chat  ->  http://localhost:3000/chat
// In production the Mini App calls the backend origin directly (whitelist the
// domain in the Zalo Mini App console) via VITE_API_BASE.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_ORIGIN || "http://localhost:3000";

  return {
    plugins: [react()],
    base: "",
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: backend,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
    build: {
      outDir: "www",
      emptyOutDir: true,
    },
  };
});
