import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "node:path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true, // expose on LAN for iPad/phone access, matching Streamlit setup
  },
  build: {
    rollupOptions: {
      output: {
        // Heavy vendor libs used across most pages — split out of the main
        // chunk so they cache independently of app code and don't bloat
        // every route's critical-path bundle.
        manualChunks: {
          recharts: ["recharts"],
          "radix-ui": [
            "@radix-ui/react-checkbox",
            "@radix-ui/react-dialog",
            "@radix-ui/react-select",
            "@radix-ui/react-slot",
            "@radix-ui/react-tabs",
            "@radix-ui/react-tooltip",
          ],
        },
      },
    },
  },
})
