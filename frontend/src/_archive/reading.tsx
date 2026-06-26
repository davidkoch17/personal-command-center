import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible } from "@/components/ui/collapsible"
import { useReading, parseBook } from "@/hooks/useReading"
import { cn } from "@/lib/utils"

export function Reading() {
  const { data, isLoading, isError } = useReading()

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">reading</h1>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">could not load reading list. backend on :8000?</p>
        </Panel>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-3">
          <BookColumn title="reading now" items={data?.reading_now ?? []} dotColor="accent" />
          <BookColumn title="to read" items={data?.to_read ?? []} dotColor="warning" />
          <BookColumn title="done" items={data?.done ?? []} dotColor="success" dimmed />
        </div>
      )}

      <Collapsible title="classics to confirm" meta="manual">
        <p className="text-sm text-text-label">
          the “classics to confirm” section of reading_list.md isn't parsed by the api
          (only to-read / reading-now / done are). confirm those directly in the vault file.
        </p>
      </Collapsible>
    </div>
  )
}

function BookColumn({
  title,
  items,
  dotColor,
  dimmed = false,
}: {
  title: string
  items: string[]
  dotColor: "accent" | "warning" | "success"
  dimmed?: boolean
}) {
  return (
    <Panel title={title} meta={`${items.length}`} statusDotColor={dotColor}>
      {items.length === 0 ? (
        <p className="text-sm text-text-label">empty</p>
      ) : (
        <ul className="space-y-2">
          {items.map((raw, i) => {
            const { title: bookTitle, author } = parseBook(raw)
            return (
              <li key={i} className={cn(dimmed && "opacity-60")}>
                <div className="text-sm text-text">{bookTitle}</div>
                {author && <div className="text-xs text-text-secondary">{author}</div>}
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}
