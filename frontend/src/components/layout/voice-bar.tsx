import { cn } from "@/lib/utils"

/** Static waveform glyph — bars sized in a fixed pattern (animates in phase 13). */
function Waveform({ active = false }: { active?: boolean }) {
  const bars = [6, 11, 8, 14, 9, 5, 12, 7]
  return (
    <div className="flex items-end gap-0.5" aria-hidden>
      {bars.map((h, i) => (
        <span
          key={i}
          className={cn(
            "w-0.5 rounded-full transition-colors",
            active ? "bg-accent" : "bg-text-label",
          )}
          style={{ height: `${h}px` }}
        />
      ))}
    </div>
  )
}

/**
 * Persistent push-to-talk bar, pinned bottom-center. Phase 12f gives it its
 * final visual language (idle dot + label + static waveform, smooth opacity
 * transitions); Phase 13 wires the actual voice states.
 */
export function VoiceBar() {
  return (
    <div className="no-print fixed bottom-4 left-1/2 z-50 -translate-x-1/2 px-2">
      <div
        className={cn(
          "panel flex items-center gap-3 bg-bg-panel/95 px-4 py-2 backdrop-blur",
          "opacity-90 transition-opacity duration-300 hover:opacity-100",
        )}
      >
        <div className="h-2 w-2 rounded-full bg-text-label" />
        <span className="label">push to talk</span>
        <Waveform />
        <span className="hidden text-xs text-text-secondary sm:inline">— phase 13</span>
      </div>
    </div>
  )
}
