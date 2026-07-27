import { useState } from "react"
import { Panel } from "@/components/ui/panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  useCashflowCategories,
  useCashflowNeedsReview,
  useResolveCashflowEntry,
  type CashflowNeedsReviewEntry,
} from "@/hooks/useCashflow"
import { formatCurrency } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

/** True when the question is about which category the entry belongs in
 * (renders a category dropdown) rather than some other ambiguity (renders a
 * free-text field instead). */
function isCategoryQuestion(question: string | null): boolean {
  return !!question && /categor/i.test(question)
}

/**
 * "Needs review" queue — flagged cashflow ledger entries Claude wasn't sure
 * how to categorize/classify while ingesting a statement. Replaces the old
 * ad-hoc questions doc for small ongoing items (see modules/finance/cashflow.py
 * docstring for the ingestion convention).
 */
export function ReviewQueue() {
  const needsReview = useCashflowNeedsReview()
  const categories = useCashflowCategories()
  const resolve = useResolveCashflowEntry()
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const entries = needsReview.data?.entries ?? []
  if (needsReview.isLoading || entries.length === 0) return null

  function draftFor(e: CashflowNeedsReviewEntry): string {
    // Category questions default to blank (forces an explicit pick, since the
    // entry's existing category is usually just a placeholder like
    // "Uncategorized"); free-text questions prefill with any existing note.
    return drafts[e.id] ?? (isCategoryQuestion(e.question) ? "" : e.notes ?? "")
  }

  function resolveEntry(e: CashflowNeedsReviewEntry) {
    const value = draftFor(e).trim()
    const fields = isCategoryQuestion(e.question) ? { category: value } : { notes: value }
    resolve.mutate(
      { id: e.id, ...fields },
      {
        onSuccess: () => {
          toast.success("entry resolved", e.description || e.category)
          setDrafts((d) => {
            const next = { ...d }
            delete next[e.id]
            return next
          })
        },
        onError: (err) => toast.error("could not resolve entry", String(err)),
      },
    )
  }

  return (
    <Panel title="needs review" meta={`${entries.length} flagged`} statusDotColor="warning">
      <div className="space-y-3">
        {entries.map((e) => {
          const options =
            (e.direction === "income" ? categories.data?.income_categories : categories.data?.expense_categories) ?? []
          return (
            <div key={e.id} className="rounded border border-border p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-text">{e.description || e.category}</p>
                  <p className="font-mono text-xs text-text-label">
                    {e.date} · {e.direction === "income" ? "+" : "−"}
                    {formatCurrency(e.amount)}
                    {e.account ? ` · ${e.account}` : ""}
                  </p>
                </div>
              </div>
              <p className="mt-2 text-sm text-warning">{e.question}</p>
              <div className="mt-2 flex items-center gap-2">
                {isCategoryQuestion(e.question) ? (
                  <Select value={draftFor(e)} onValueChange={(v) => setDrafts((d) => ({ ...d, [e.id]: v }))}>
                    <SelectTrigger className="h-8 w-48">
                      <SelectValue placeholder="choose a category…" />
                    </SelectTrigger>
                    <SelectContent>
                      {options.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    className="h-8 flex-1"
                    value={draftFor(e)}
                    onChange={(ev) => setDrafts((d) => ({ ...d, [e.id]: ev.target.value }))}
                    placeholder="your answer…"
                  />
                )}
                <Button size="sm" onClick={() => resolveEntry(e)} disabled={resolve.isPending || !draftFor(e).trim()}>
                  resolve
                </Button>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
