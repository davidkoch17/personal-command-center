import { useState, useRef } from "react"
import { api, API_BASE } from "@/lib/api"

export type JarvisState = "idle" | "thinking" | "speaking" | "listening" | "routing"

interface BriefingResponse {
  text: string
  suggestions: string[]
  spoken: string
}

/** Shape of `/api/voice/route` — the 8-category router output. */
interface RouteResponse {
  action?: string
  navigate_to?: string
  skill_name?: string
  skill_args?: Record<string, unknown>
  capture_text?: string
  task_text?: string
  task_section?: string
  toggle_match?: string
  hypothesis_ticker?: string
  hypothesis_text?: string
  transaction?: {
    ticker: string
    action: string
    quantity: number
    price: number
    currency?: string
    fees?: number
    notes?: string | null
  }
  clarification_question?: string
  answer?: string
  spoken_response?: string
}

/**
 * Drives the entire Jarvis flow with no overlay — the ball IS the UX.
 *
 * Flow: assemble briefing → speak it (Piper, male British) → listen with
 * silence detection (stops after 1.5s of quiet, max 15s) → transcribe (Whisper)
 * → route (Claude, 8 categories) → execute the action (navigate / data_query /
 * run_skill / capture_inbox / add_task / toggle_task / add_hypothesis /
 * ambiguous / unclear) → speak a confirmation. Ambiguous commands are
 * multi-turn: Jarvis asks back and listens again (up to two follow-ups).
 *
 * Returns the ball `state`, a short `subtitle` (echoes what was heard), and a
 * `trigger`: clicking while idle starts the flow; clicking while busy CANCELS
 * (stops audio, aborts fetches, returns to idle, says "Cancelled.").
 */
export function useJarvisBriefing() {
  const [state, setState] = useState<JarvisState>("idle")
  const [subtitle, setSubtitle] = useState<string>("")

  // Playback + capture handles, kept in refs so cancel can tear them all down.
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioResolveRef = useRef<(() => void) | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const cancelledRef = useRef(false)
  const runningRef = useRef(false)
  const suggestionsRef = useRef<string[]>([])

  // ---- low-level helpers (only touch refs + stable setters) ----

  function teardownMic() {
    try {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop()
      }
    } catch {
      /* noop */
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      void audioContextRef.current.close()
    }
    recorderRef.current = null
    streamRef.current = null
    audioContextRef.current = null
  }

  function stopAudio() {
    if (audioRef.current) {
      try {
        audioRef.current.pause()
      } catch {
        /* noop */
      }
      audioRef.current = null
    }
    // Unblock any awaiter parked on a play() promise.
    if (audioResolveRef.current) {
      const resolve = audioResolveRef.current
      audioResolveRef.current = null
      resolve()
    }
  }

  /** Synthesize `text` via Piper and play it to completion (no state change). */
  async function synthAndPlay(text: string, signal?: AbortSignal): Promise<void> {
    const res = await fetch(`${API_BASE}/api/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal,
    })
    const url = URL.createObjectURL(await res.blob())
    await new Promise<void>((resolve) => {
      const audio = new Audio(url)
      audioRef.current = audio
      const done = () => {
        audioResolveRef.current = null
        URL.revokeObjectURL(url)
        resolve()
      }
      audioResolveRef.current = done
      audio.onended = done
      audio.onerror = done
      void audio.play().catch(done)
    })
  }

  /** Speak a butler-style line: switch the ball to speaking + show it as subtitle. */
  async function playSpoken(text: string): Promise<void> {
    if (cancelledRef.current || !text) return
    setState("speaking")
    setSubtitle(text)
    await synthAndPlay(text, abortRef.current?.signal)
  }

  /** POST JSON to a voice endpoint, abortable via the active controller. */
  async function voiceJson<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abortRef.current?.signal,
    })
    return (await res.json()) as T
  }

  /**
   * Record from the mic, stopping on silence. Stops after `silenceMs` of quiet
   * (once at least 1s has elapsed) or at `maxDurationMs`, whichever comes first.
   * Resolves with the recorded webm Blob.
   */
  function recordWithSilenceDetection(
    maxDurationMs = 15000,
    silenceMs = 2000,
    silenceThreshold = -50,
  ): Promise<Blob> {
    return new Promise<Blob>((resolve, reject) => {
      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .then((stream) => {
          streamRef.current = stream
          const audioContext = new AudioContext()
          audioContextRef.current = audioContext
          const source = audioContext.createMediaStreamSource(stream)
          const analyser = audioContext.createAnalyser()
          analyser.fftSize = 2048
          source.connect(analyser)

          const mediaRecorder = new MediaRecorder(stream)
          recorderRef.current = mediaRecorder
          const chunks: Blob[] = []
          mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunks.push(e.data)
          }
          mediaRecorder.start()

          const startTime = Date.now()
          let lastSoundTime = startTime
          let lastDb = -Infinity
          let peakDb = -Infinity
          const dataArray = new Float32Array(analyser.fftSize)

          const finish = () => {
            // Client-side debug: how long we captured + the loudest level seen.
            // eslint-disable-next-line no-console
            console.debug(
              `[jarvis] recording done: ${((Date.now() - startTime) / 1000).toFixed(2)}s, ` +
                `peak ${peakDb.toFixed(1)}dB, last ${lastDb.toFixed(1)}dB`,
            )
            mediaRecorder.onstop = () => resolve(new Blob(chunks, { type: "audio/webm" }))
            try {
              if (mediaRecorder.state !== "inactive") mediaRecorder.stop()
              else resolve(new Blob(chunks, { type: "audio/webm" }))
            } catch {
              resolve(new Blob(chunks, { type: "audio/webm" }))
            }
            stream.getTracks().forEach((t) => t.stop())
            if (audioContext.state !== "closed") void audioContext.close()
          }

          const check = () => {
            if (cancelledRef.current) {
              finish()
              return
            }
            analyser.getFloatTimeDomainData(dataArray)
            // RMS volume in dB.
            let sum = 0
            for (let i = 0; i < dataArray.length; i++) sum += dataArray[i] * dataArray[i]
            const rms = Math.sqrt(sum / dataArray.length)
            const db = 20 * Math.log10(rms || 0.0001)
            lastDb = db
            if (db > peakDb) peakDb = db

            const now = Date.now()
            if (db > silenceThreshold) lastSoundTime = now

            const totalElapsed = now - startTime
            const silenceElapsed = now - lastSoundTime

            // Stop on max duration, or after sound-then-silence (min 1s total).
            if (totalElapsed > maxDurationMs || (totalElapsed > 1000 && silenceElapsed > silenceMs)) {
              finish()
            } else {
              requestAnimationFrame(check)
            }
          }
          requestAnimationFrame(check)
        })
        .catch(reject)
    })
  }

  /**
   * Perform the side-effect for a routed command (everything except the
   * multi-turn ``ambiguous`` dance, which the callers own). Shared by the voice
   * flow and the typed-input flow so both behave identically.
   */
  async function executeRoute(route: RouteResponse): Promise<void> {
    switch (route.action) {
      case "navigate":
        if (route.navigate_to) window.open(route.navigate_to, "_blank")
        break

      case "data_query":
        // The answer rides in route.answer / spoken_response — nothing to do.
        break

      case "run_skill":
        if (route.skill_name) {
          await api.post(`/api/skills/${route.skill_name}/run`, {
            args: route.skill_args || {},
          })
        }
        break

      case "capture_inbox":
        if (route.capture_text) {
          await api.post("/api/inbox/capture", {
            content: route.capture_text,
            source: "jarvis",
          })
        }
        break

      case "add_task":
        if (route.task_text) {
          await api.post("/api/tasks/add", {
            section: route.task_section || "Bigger items",
            text: route.task_text,
          })
        }
        break

      case "toggle_task":
        if (route.toggle_match) {
          await api.post("/api/tasks/toggle-by-text", { match: route.toggle_match })
        }
        break

      case "add_hypothesis":
        if (route.hypothesis_ticker && route.hypothesis_text) {
          await api.post(
            `/api/watchlist/${encodeURIComponent(route.hypothesis_ticker)}/hypothesis`,
            { text: route.hypothesis_text },
          )
        }
        break

      case "add_transaction":
        if (route.transaction?.ticker) {
          const t = route.transaction
          await api.post("/api/finance/transactions", {
            date: new Date().toISOString().slice(0, 10),
            ticker: t.ticker.toUpperCase(),
            action: t.action || "buy",
            quantity: t.quantity,
            price: t.price,
            currency: t.currency || "USD",
            fees: t.fees ?? 0,
            notes: t.notes ?? "Logged via Jarvis voice command",
          })
        }
        break

      case "unclear":
      default:
        break
    }
  }

  /**
   * Listen → transcribe → route → execute. Recurses for ambiguous commands
   * (Jarvis asks a clarifying question and listens again), capped at 2 follow-ups.
   */
  async function recordAndRoute(depth: number): Promise<void> {
    if (cancelledRef.current) return

    // 1. Listen (silence-detected).
    setState("listening")
    setSubtitle("listening…")
    const audioBlob = await recordWithSilenceDetection()
    if (cancelledRef.current) return

    // 2. Transcribe.
    setState("routing")
    setSubtitle("thinking…")
    const formData = new FormData()
    formData.append("audio", audioBlob, "rec.webm")
    const transcribeRes = await fetch(`${API_BASE}/api/voice/transcribe`, {
      method: "POST",
      body: formData,
      signal: abortRef.current?.signal,
    })
    const { text: transcript, error: transcribeError } =
      (await transcribeRes.json()) as { text: string; error?: string }
    if (cancelledRef.current) return

    const heard = (transcript || "").trim()
    // Surface a clear reason instead of failing silently when nothing came back.
    if (transcribeError || !heard) {
      setSubtitle(
        transcribeError
          ? `couldn't transcribe (${transcribeError})`
          : "didn't catch that, try again",
      )
      await playSpoken("I didn't catch that. Could you repeat?")
      return
    }
    // Echo what Jarvis heard so David can correct course immediately.
    setSubtitle(`heard: "${heard}"`)

    // 3. Route.
    const route = await voiceJson<RouteResponse>("/api/voice/route", {
      text: heard,
      current_page: window.location.pathname,
      context: { briefing_suggestions: suggestionsRef.current },
    })
    if (cancelledRef.current) return

    // 4. Ambiguous → speak the clarification, then listen again (≤2 follow-ups).
    if (route.action === "ambiguous") {
      await playSpoken(route.spoken_response || route.clarification_question || "Could you clarify?")
      if (cancelledRef.current) return
      if (depth < 2) {
        setSubtitle(route.clarification_question || "…")
        return recordAndRoute(depth + 1)
      }
      return
    }

    // 5. Execute the action, then speak the confirmation.
    await executeRoute(route)
    if (cancelledRef.current) return
    if (route.spoken_response) {
      await playSpoken(route.spoken_response)
    }
  }

  /**
   * Typed-command path — the text input below the ball. Mirrors the voice flow
   * minus mic/transcription: route the text, run the action, speak the reply.
   * For an ambiguous command we just speak the clarification (no re-listen,
   * since the user is typing — they can simply type a clearer command).
   */
  async function triggerWithText(text: string): Promise<void> {
    if (runningRef.current) return
    runningRef.current = true
    cancelledRef.current = false
    abortRef.current = new AbortController()
    try {
      setState("routing")
      setSubtitle(`heard: "${text}"`)

      const route = await voiceJson<RouteResponse>("/api/voice/route", {
        text,
        current_page: window.location.pathname,
        context: {},
      })
      if (cancelledRef.current) return

      if (route.action === "ambiguous") {
        await playSpoken(
          route.spoken_response || route.clarification_question || "Could you clarify?",
        )
      } else {
        await executeRoute(route)
        if (cancelledRef.current) return
        if (route.spoken_response) {
          await playSpoken(route.spoken_response)
        }
      }
    } catch (e) {
      if (!cancelledRef.current) {
        console.error("Jarvis text trigger error:", e)
        setSubtitle(`error: ${(e as Error).message}`)
      }
    } finally {
      runningRef.current = false
      if (!cancelledRef.current) {
        window.setTimeout(() => {
          if (!runningRef.current) {
            setState("idle")
            setSubtitle("")
          }
        }, 2000)
      }
    }
  }

  async function runFlow() {
    runningRef.current = true
    cancelledRef.current = false
    abortRef.current = new AbortController()
    try {
      // 1. Assemble the briefing.
      setState("thinking")
      setSubtitle("assembling briefing")
      const briefing = await voiceJson<BriefingResponse>("/api/voice/briefing", {})
      if (cancelledRef.current) return
      suggestionsRef.current = briefing.suggestions ?? []

      // 2. Speak the briefing.
      setState("speaking")
      setSubtitle("briefing")
      await synthAndPlay(briefing.spoken, abortRef.current.signal)
      if (cancelledRef.current) return

      // 3. Listen, route, execute (multi-turn aware).
      await recordAndRoute(0)
    } catch (e) {
      if (!cancelledRef.current) {
        console.error("Jarvis error:", e)
        setSubtitle("something went wrong")
      }
    } finally {
      teardownMic()
      runningRef.current = false
      if (!cancelledRef.current) {
        window.setTimeout(() => {
          if (!runningRef.current) {
            setState("idle")
            setSubtitle("")
          }
        }, 1500)
      }
    }
  }

  async function cancelFlow() {
    cancelledRef.current = true
    abortRef.current?.abort()
    stopAudio()
    teardownMic()
    runningRef.current = false
    setState("idle")
    setSubtitle("cancelled")
    // Spoken confirmation on a fresh request (the active controller is aborted).
    try {
      await synthAndPlay("Cancelled.")
    } catch {
      /* noop */
    }
    window.setTimeout(() => {
      if (!runningRef.current) setSubtitle("")
    }, 1500)
  }

  /** Click handler: start when idle, otherwise cancel the in-flight operation. */
  function trigger() {
    if (runningRef.current) {
      void cancelFlow()
    } else {
      void runFlow()
    }
  }

  return { state, subtitle, trigger, triggerWithText }
}
