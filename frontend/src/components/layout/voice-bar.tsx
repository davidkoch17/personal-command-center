/**
 * Persistent voice bar, pinned bottom-center on every shell page. Phase 12a is a
 * static placeholder — the Jarvis push-to-talk interaction lands in Phase 13.
 */
export function VoiceBar() {
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50">
      <div className="panel flex items-center gap-3 px-4 py-2 bg-bg-panel/95 backdrop-blur">
        <div className="w-2 h-2 rounded-full bg-text-label" />
        <span className="label">push to talk</span>
        <span className="text-text-secondary text-xs">— phase 13</span>
      </div>
    </div>
  )
}
