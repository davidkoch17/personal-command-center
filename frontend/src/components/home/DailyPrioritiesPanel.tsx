import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { Panel } from "@/components/ui/panel"

interface Suggestion {
  task: string
  rationale?: string
  deadline?: string | null
  estimated_minutes?: number
}

interface SuggestionsResponse {
  priorities?: Suggestion[]
  summary?: string
}

interface DailyItem {
  text: string
  checked: boolean
}

interface TodayResponse {
  exists: boolean
  priorities: DailyItem[]
  manual: DailyItem[]
}

/**
 * Morning anchor at the top of Home. On the first load of a day (no
 * ``99_System/Daily_Todos/YYYY-MM-DD.md`` yet) it auto-fetches 3-5 Claude
 * suggestions; David accepts them into a curated, toggleable list that persists
 * to that file. He can add manual items and regenerate suggestions any time.
 */
export function DailyPrioritiesPanel() {
  const qc = useQueryClient()
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [manualInput, setManualInput] = useState("")
  // Checkbox state for the suggestion-review view, keyed by index.
  const [picked, setPicked] = useState<Record<number, boolean>>({})

  const { data: today, isLoading } = useQuery({
    queryKey: ["daily-today"],
    queryFn: () => api.get<TodayResponse>("/api/daily/today"),
  })

  const {
    data: suggestions,
    refetch: fetchSuggestions,
    isFetching: isGenerating,
  } = useQuery({
    queryKey: ["daily-suggestions"],
    queryFn: () => api.post<SuggestionsResponse>("/api/daily/today/generate", {}),
    enabled: false,
  })

  const acceptMutation = useMutation({
    mutationFn: (priorities: Suggestion[]) =>
      api.post("/api/daily/today/accept", { priorities }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["daily-today"] })
      setShowSuggestions(false)
    },
  })

  const addMutation = useMutation({
    mutationFn: (text: string) => api.post("/api/daily/today/add", { text }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["daily-today"] })
      setManualInput("")
    },
  })

  const toggleMutation = useMutation({
    mutationFn: (text: string) => api.post("/api/daily/today/toggle", { text }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["daily-today"] }),
  })

  // Auto-generate suggestions on the first load of a day with no today file.
  useEffect(() => {
    if (today && !today.exists) {
      setShowSuggestions(true)
      void fetchSuggestions()
    }
  }, [today, fetchSuggestions])

  // Default every freshly-generated suggestion to checked.
  useEffect(() => {
    if (suggestions?.priorities) {
      setPicked(Object.fromEntries(suggestions.priorities.map((_, i) => [i, true])))
    }
  }, [suggestions])

  if (isLoading) return null

  // --- Suggestions review (before any priorities accepted) ------------------
  if (showSuggestions && suggestions) {
    const list = suggestions.priorities ?? []
    return (
      <Panel title="today's priorities" meta="suggestions" statusDotColor="accent">
        {isGenerating ? (
          <p className="text-text-secondary text-sm">generating suggestions…</p>
        ) : list.length === 0 ? (
          <p className="text-text-label text-sm">no suggestions — try regenerating.</p>
        ) : (
          <>
            {suggestions.summary && (
              <p className="text-text-secondary text-sm mb-3">{suggestions.summary}</p>
            )}
            <div className="space-y-2 mb-4">
              {list.map((p, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 p-2 hover:bg-bg-panel-hover rounded"
                >
                  <input
                    type="checkbox"
                    checked={picked[i] ?? true}
                    onChange={(e) =>
                      setPicked((prev) => ({ ...prev, [i]: e.target.checked }))
                    }
                    className="mt-1"
                    id={`sug-${i}`}
                  />
                  <label htmlFor={`sug-${i}`} className="flex-1 text-sm cursor-pointer">
                    <div className="text-text">{p.task}</div>
                    {p.rationale && (
                      <div className="text-text-label text-xs italic">{p.rationale}</div>
                    )}
                  </label>
                </div>
              ))}
            </div>
            <button
              className="px-4 py-2 bg-accent text-bg rounded-md text-sm font-medium hover:bg-accent-dim disabled:opacity-50"
              disabled={acceptMutation.isPending}
              onClick={() =>
                acceptMutation.mutate(list.filter((_, i) => picked[i] ?? true))
              }
            >
              accept these as today's priorities
            </button>
          </>
        )}
      </Panel>
    )
  }

  // --- Today's curated list -------------------------------------------------
  const all = [...(today?.priorities ?? []), ...(today?.manual ?? [])]
  const doneCount = all.filter((x) => x.checked).length
  return (
    <Panel
      title={`today — ${new Date().toISOString().slice(0, 10)}`}
      meta={`${doneCount}/${all.length} done`}
      statusDotColor="accent"
    >
      {all.length === 0 ? (
        <p className="text-text-label text-sm">no priorities yet for today.</p>
      ) : (
        <div className="space-y-1">
          {all.map((item, i) => (
            <div
              key={i}
              className="flex items-center gap-3 py-1 cursor-pointer hover:bg-bg-panel-hover rounded px-2"
              onClick={() => toggleMutation.mutate(item.text)}
            >
              <input type="checkbox" checked={item.checked} readOnly />
              <span className={item.checked ? "line-through text-text-disabled" : "text-text"}>
                {item.text}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <input
          type="text"
          value={manualInput}
          onChange={(e) => setManualInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && manualInput.trim()) {
              addMutation.mutate(manualInput.trim())
            }
          }}
          placeholder="add to today..."
          className="flex-1 bg-bg-panel border border-border rounded px-3 py-2 text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none"
        />
        <button
          className="px-3 py-2 text-text-secondary hover:text-text text-sm disabled:opacity-50"
          onClick={() => {
            setShowSuggestions(true)
            void fetchSuggestions()
          }}
          disabled={isGenerating}
        >
          regenerate suggestions
        </button>
      </div>
    </Panel>
  )
}
