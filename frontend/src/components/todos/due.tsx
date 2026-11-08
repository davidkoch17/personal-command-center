import { Tag } from "@/components/ui/tag"

/** Whole days from today (local time) to an ISO date; negative = overdue. */
export function daysUntil(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number)
  const target = new Date(y, m - 1, d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

/** Due-date pill: overdue = danger (wine), ≤ 7 days = warning (camel). */
export function DueTag({ due, done }: { due: string | null; done: boolean }) {
  if (!due) return null
  const days = daysUntil(due)
  const rel = days === 0 ? "today" : days < 0 ? `${-days}d overdue` : `in ${days}d`
  const variant = done ? "muted" : days < 0 ? "danger" : days <= 7 ? "warning" : "muted"
  return (
    <Tag variant={variant} className="font-mono normal-case tracking-normal">
      {rel} · {due}
    </Tag>
  )
}
