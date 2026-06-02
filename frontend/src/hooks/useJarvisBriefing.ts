import { useState, useRef, useCallback } from "react"
import { api, API_BASE } from "@/lib/api"

export type JarvisState = "idle" | "thinking" | "speaking" | "listening" | "routing"

interface BriefingResponse {
  text: string
  suggestions: string[]
  spoken: string
}

interface RouteResponse {
  action?: string
  navigate_to?: string
  skill_name?: string
  skill_args?: Record<string, unknown>
  capture_text?: string
  spoken_response?: string
}

/**
 * Drives the whole Jarvis briefing flow with no overlay — the ball IS the UX.
 * Returns the current `state` (for the ball's visual), a short `subtitle`
 * (rendered under the ball), and a `trigger` to start the flow on click.
 *
 * Flow: assemble briefing → speak it (Piper) → listen 5s (mic) → transcribe +
 * route → open the target page in a NEW TAB / run a skill / capture to inbox,
 * with a brief spoken confirmation. Every step degrades gracefully — failures
 * surface a subtitle and return the ball to idle.
 */
export function useJarvisBriefing() {
  const [state, setState] = useState<JarvisState>("idle")
  const [subtitle, setSubtitle] = useState<string>("")
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const trigger = useCallback(async () => {
    if (state !== "idle") return

    try {
      setState("thinking")
      setSubtitle("assembling briefing")

      // 1. Get briefing
      const briefing = await api.post<BriefingResponse>("/api/voice/briefing", {})

      // 2. Speak it (Piper)
      setState("speaking")
      setSubtitle("briefing")
      const speakRes = await fetch(`${API_BASE}/api/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: briefing.spoken }),
      })
      const audioBlob = await speakRes.blob()

      audioRef.current = new Audio(URL.createObjectURL(audioBlob))
      await new Promise<void>((resolve, reject) => {
        if (!audioRef.current) return reject()
        audioRef.current.onended = () => resolve()
        audioRef.current.onerror = () => reject()
        void audioRef.current.play()
      })

      // 3. Listen for response (5 sec)
      setState("listening")
      setSubtitle("listening...")
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mediaRecorderRef.current = new MediaRecorder(stream)
      const chunks: Blob[] = []
      mediaRecorderRef.current.ondataavailable = (e) => chunks.push(e.data)
      mediaRecorderRef.current.start()

      await new Promise((resolve) => setTimeout(resolve, 5000))
      mediaRecorderRef.current.stop()
      stream.getTracks().forEach((t) => t.stop())

      await new Promise((resolve) => {
        mediaRecorderRef.current!.onstop = resolve
      })

      // 4. Transcribe + route
      setState("routing")
      setSubtitle("thinking...")

      const blob = new Blob(chunks, { type: "audio/webm" })
      const formData = new FormData()
      formData.append("audio", blob, "rec.webm")
      const transcribeRes = await fetch(`${API_BASE}/api/voice/transcribe`, {
        method: "POST",
        body: formData,
      })
      const { text: transcript } = (await transcribeRes.json()) as { text: string }

      if (transcript) {
        setSubtitle(`"${transcript}"`)
        const route = await api.post<RouteResponse>("/api/voice/route", {
          text: transcript,
          current_page: window.location.pathname,
          context: { briefing_suggestions: briefing.suggestions },
        })

        // 5. Open target page in NEW TAB
        if (route.action === "navigate" && route.navigate_to) {
          window.open(route.navigate_to, "_blank")
        } else if (route.action === "run_skill" && route.skill_name) {
          await api.post(`/api/skills/${route.skill_name}/run`, { args: route.skill_args })
        } else if (route.action === "capture_inbox" && route.capture_text) {
          await api.post("/api/inbox/capture", { text: route.capture_text })
        }

        // Brief audio confirmation
        if (route.spoken_response) {
          setState("speaking")
          setSubtitle(route.spoken_response)
          const confirmRes = await fetch(`${API_BASE}/api/voice/speak`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: route.spoken_response }),
          })
          const confirmAudio = new Audio(URL.createObjectURL(await confirmRes.blob()))
          await new Promise((resolve) => {
            confirmAudio.onended = resolve
            void confirmAudio.play()
          })
        }
      }
    } catch (e) {
      console.error("Jarvis error:", e)
      setSubtitle("something went wrong")
    } finally {
      setTimeout(() => {
        setState("idle")
        setSubtitle("")
      }, 1500)
    }
  }, [state])

  return { state, subtitle, trigger }
}
