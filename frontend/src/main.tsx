import React from "react"
import ReactDOM from "react-dom/client"
import App from "@/App"
import { useUpdateStore } from "@/lib/update-store"
import "@/globals.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Register the service worker so the app is installable as a PWA (iPhone "Add
// to Home Screen") and the shell stays available offline. Dev (Vite, port 5173)
// has no sw.js, so only register in production where the backend serves it.
if ("serviceWorker" in navigator && !import.meta.env.DEV) {
  window.addEventListener("load", () => {
    // Chunk 9.8: a new deploy's SW calls skipWaiting()+clients.claim() on its
    // own (see sw.js), so it takes over an already-open tab without the usual
    // "waiting" phase — but this tab's in-memory JS/CSS is still the old
    // build until reloaded. `controllerchange` fires exactly when that
    // takeover happens; a controller already present *before* registering
    // means this tab was already being served by an older SW, so that event
    // is a genuine update, not the very first install claiming a fresh tab
    // (which never had a controller to begin with, so the check below skips it).
    const hadControllerAtLoad = Boolean(navigator.serviceWorker.controller)
    navigator.serviceWorker
      .register("/sw.js")
      .then(() => {
        navigator.serviceWorker.addEventListener("controllerchange", () => {
          if (hadControllerAtLoad) useUpdateStore.getState().markAvailable()
        })
      })
      .catch((err) => {
        console.warn("Service worker registration failed:", err)
      })
  })
}
