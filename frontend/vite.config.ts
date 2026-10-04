import { defineConfig, type Plugin } from "vite"
import react from "@vitejs/plugin-react"
import path from "node:path"
import { createHash } from "node:crypto"
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs"

/**
 * Chunk 9.8 — substitutes sw.js's __BUILD_HASH__ placeholder with a real hash
 * once the build is written to disk, so every production build that actually
 * changes an asset gets a genuinely new service-worker cache name (see
 * public/sw.js's own comment on why "cc-shell-v1" never changing was the root
 * cause of every deploy going stale on already-open browsers/PWAs).
 *
 * The hash is derived from dist/assets' own filenames, not a timestamp — Vite
 * already content-hashes every asset, so the set of filenames only changes
 * when something real changed, and a no-op rebuild doesn't needlessly evict
 * caches that are still correct.
 *
 * Fails the build (not a console warning) if the placeholder is ever missing
 * from dist/sw.js — a silently no-op substitution is exactly the bug this
 * exists to prevent recurring.
 */
function swCacheBust(): Plugin {
  return {
    name: "sw-cache-bust",
    closeBundle() {
      const outDir = path.resolve(__dirname, "dist")
      const assetsDir = path.join(outDir, "assets")
      const swPath = path.join(outDir, "sw.js")

      if (!existsSync(assetsDir) || !existsSync(swPath)) return // not a client build (e.g. SSR) — nothing to do

      const files = readdirSync(assetsDir).sort()
      const hash = createHash("sha256").update(files.join("|")).digest("hex").slice(0, 10)

      const sw = readFileSync(swPath, "utf-8")
      if (!sw.includes("__BUILD_HASH__")) {
        throw new Error(
          "sw-cache-bust: dist/sw.js has no __BUILD_HASH__ placeholder to substitute — " +
            "the service worker's cache name would silently stay whatever was last built, " +
            "reintroducing the stale-deploy bug (Chunk 9.8). Check public/sw.js's CACHE constant.",
        )
      }
      writeFileSync(swPath, sw.replaceAll("__BUILD_HASH__", hash), "utf-8")
      console.log(`[sw-cache-bust] cc-shell-${hash}`)
    },
  }
}

export default defineConfig({
  plugins: [react(), swCacheBust()],
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
