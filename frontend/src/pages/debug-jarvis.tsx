import { useState } from "react"
import { api } from "@/lib/api"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useJarvisBriefing } from "@/hooks/useJarvisBriefing"

/**
 * Hidden dev tool (not in the sidebar — reachable from Settings → "debug jarvis"
 * or directly at ``/debug-jarvis``). Sends a typed command straight to
 * ``/api/voice/route`` so the router can be exercised without the mic.
 *
 * Use it to bisect a Jarvis "disconnect": if "route only" returns the right
 * action here but voice doesn't fire, the problem is in the voice (STT) layer;
 * if "route only" is already wrong, it's the router/prompt. "Route + execute"
 * runs the real action handler (navigate / write to vault / etc.) and speaks
 * back, surfacing any failure as a toast — exactly what the ball does.
 */
export function DebugJarvis() {
  const [text, setText] = useState("")
  const [routeResult, setRouteResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { state, subtitle, triggerWithText } = useJarvisBriefing()

  async function testRoute() {
    setBusy(true)
    setError(null)
    setRouteResult(null)
    try {
      const result = await api.post("/api/voice/route", {
        text,
        current_page: window.location.pathname,
        context: {},
      })
      setRouteResult(result)
      // Mirror the backend trace in the browser console for quick scanning.
      console.log("[DebugJarvis] route result:", result)
    } catch (e) {
      const msg = (e as Error).message
      setError(msg)
      console.error("[DebugJarvis] route failed:", msg, e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">jarvis debug</h1>
        <p className="mt-1 text-sm text-text-secondary">
          type a command to test the router (and optionally execute it) without voice.
        </p>
      </div>

      <Panel title="command" statusDotColor="accent">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void testRoute()
          }}
          placeholder='e.g. "open Ulli" · "show me Nike" · "mark FFM apartment done"'
          className="mb-3"
        />
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" size="sm" disabled={busy || !text.trim()} onClick={() => void testRoute()}>
            {busy ? "routing…" : "route only (no execute)"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={busy || !text.trim()}
            onClick={() => void triggerWithText(text)}
          >
            route + execute
          </Button>
        </div>
        <div className="mt-3 font-mono text-xs text-text-secondary">
          ball state: <span className="text-accent">{state}</span>
          {subtitle && <span className="ml-2">· {subtitle}</span>}
        </div>
      </Panel>

      {error && (
        <Panel title="route error" statusDotColor="danger">
          <pre className="whitespace-pre-wrap font-mono text-xs text-danger">{error}</pre>
        </Panel>
      )}

      {routeResult != null && (
        <Panel title="backend response" statusDotColor="muted">
          <pre className="overflow-x-auto rounded-sm bg-bg-panel p-4 font-mono text-xs text-text">
            {JSON.stringify(routeResult, null, 2)}
          </pre>
        </Panel>
      )}
    </div>
  )
}
