import React from "react"
import ReactDOM from "react-dom/client"
import App from "@/App"
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
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("Service worker registration failed:", err)
    })
  })
}
