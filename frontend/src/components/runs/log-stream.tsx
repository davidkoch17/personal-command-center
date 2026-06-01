import { useEffect, useRef, useState } from "react"
import { API_BASE } from "@/lib/api"

/**
 * Live log viewer over the run's WebSocket. The backend streams a full log
 * snapshot for already-finished runs and incremental deltas for active ones, so
 * this works for any run state. Auto-scrolls to the tail.
 */
export function LogStream({ runId }: { runId: string }) {
  const [log, setLog] = useState("")
  const [connected, setConnected] = useState(false)
  const [closed, setClosed] = useState(false)
  const ref = useRef<HTMLPreElement>(null)

  useEffect(() => {
    setLog("")
    setClosed(false)
    const wsUrl =
      API_BASE.replace(/^http/, "ws") +
      `/api/runs/${encodeURIComponent(runId)}/stream`
    let ws: WebSocket
    try {
      ws = new WebSocket(wsUrl)
    } catch {
      setClosed(true)
      return
    }
    ws.onopen = () => setConnected(true)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as { type: string; data: unknown }
        if (msg.type === "log" && typeof msg.data === "string") {
          setLog((l) => l + msg.data)
        }
      } catch {
        /* ignore malformed frames */
      }
    }
    ws.onclose = () => setClosed(true)
    ws.onerror = () => setClosed(true)
    return () => ws.close()
  }, [runId])

  useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [log])

  return (
    <pre
      ref={ref}
      className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-sm border border-border bg-bg p-2 font-mono text-xs text-text-secondary"
    >
      {log || (closed ? "(no log output)" : connected ? "streaming…" : "connecting…")}
    </pre>
  )
}
