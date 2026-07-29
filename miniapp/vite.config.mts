import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Zalo Mini App loads JS/CSS from app-config.json (classic scripts), not from
// index.html. Strip Vite's injected <script type=module>/<link> on build so the
// bundle isn't loaded twice; index.html is left as the bare `#app` shell.
function zaloShellHtml() {
  return {
    name: "zalo-shell-html",
    apply: "build" as const,
    transformIndexHtml(html: string) {
      return html
        .replace(/\s*<script[^>]*index\.js[^>]*><\/script>/g, "")
        .replace(/\s*<link[^>]*index\.css[^>]*>/g, "");
    },
  };
}

// The TripSmart backend (FastAPI) exposes POST /chat but sets NO CORS headers.
// We are NOT allowed to modify the backend, so in local browser dev we avoid
// CORS entirely by proxying:  /api/chat  ->  http://localhost:3000/chat
// In production the Mini App calls the backend origin directly (whitelist the
// domain in the Zalo Mini App console) via VITE_API_BASE.
export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.BACKEND_ORIGIN || "http://localhost:3000";

  return {
    plugins: [react(), zaloShellHtml()],
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
    // Zalo Mini App's loader wants a CLASSIC script (no ES modules) referenced
    // from app-config.json, not Vite's default `<script type="module">`. So build
    // one self-contained IIFE bundle with fixed (unhashed) names:
    //   www/assets/index.js  + www/assets/index.css
    // These are declared in app-config.json (listSyncJS / listCSS).
    build: {
      outDir: "www",
      emptyOutDir: true,
      target: "es2015",
      cssCodeSplit: false,
      rollupOptions: {
        output: {
          format: "iife",
          inlineDynamicImports: true,
          entryFileNames: "assets/index.js",
          assetFileNames: "assets/index.[ext]",
        },
      },
    },
  };
});
