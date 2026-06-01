import { useEffect, useRef, useState } from "react"

/**
 * Tween a number toward `target` over `duration` ms (ease-out). Used to animate
 * metric changes (e.g. portfolio value after a refresh). Honors reduced-motion
 * by snapping. Returns the current interpolated value.
 */
export function useTween(target: number | null | undefined, duration = 300): number | null {
  const [value, setValue] = useState<number | null>(target ?? null)
  const fromRef = useRef<number>(target ?? 0)
  const rafRef = useRef<number>()

  useEffect(() => {
    if (target == null || Number.isNaN(target)) {
      setValue(target ?? null)
      return
    }
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    const from = fromRef.current
    if (reduce || from === target) {
      fromRef.current = target
      setValue(target)
      return
    }

    const start = performance.now()
    const delta = target - from
    function frame(now: number) {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3) // ease-out cubic
      const current = from + delta * eased
      setValue(current)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(frame)
      } else {
        fromRef.current = target!
      }
    }
    rafRef.current = requestAnimationFrame(frame)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [target, duration])

  return value
}
