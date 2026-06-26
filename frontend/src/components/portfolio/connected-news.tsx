import { Skeleton } from "@/components/ui/skeleton"
import { Tag } from "@/components/ui/tag"
import { useConnectedNews, type Capture } from "@/hooks/usePortfolioHub"
import { cn } from "@/lib/utils"

/**
 * Connected News per position — LOCKED structure (spec § d, do not redesign):
 *   1. SectorSummaryCard  — compact sector chips (counts of linked captures).
 *   2. BigMovesBanner     — highlighted; fires on day move > 5% OR a >=3/48h cluster.
 *   3. ConnectedNewsList  — every linked capture, newest first, NO truncation/pagination.
 */
export function ConnectedNews({ ticker, enabled }: { ticker: string; enabled: boolean }) {
  const { data, isLoading } = useConnectedNews(ticker, enabled)

  if (isLoading) return <Skeleton className="h-24" />
  if (!data) return null

  return (
    <div className="space-y-3">
      {/* 1. Sector summary chips */}
      <SectorSummaryCard sectors={data.sectors} />

      {/* 2. Big-moves banner (prominent) */}
      {data.big_moves.length > 0 && <BigMovesBanner moves={data.big_moves} />}

      {/* 3. Connected news list — full, chronological, no truncation */}
      <div>
        <div className="label mb-1">connected news · {data.count}</div>
        {data.captures.length === 0 ? (
          <p className="text-xs text-text-label">no captures linked to {ticker} yet.</p>
        ) : (
          <ul className="space-y-2">
            {data.captures.map((c) => (
              <ConnectedNewsRow key={c.id} capture={c} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function SectorSummaryCard({ sectors }: { sectors: { sector: string; count: number }[] }) {
  return (
    <div className="rounded-sm border border-border bg-bg-panel px-3 py-2">
      <div className="label mb-1.5">sector summary</div>
      {sectors.length === 0 ? (
        <p className="text-xs text-text-label">no sector-tagged captures yet.</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {sectors.map((s) => (
            <span key={s.sector} className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-bg px-2 py-0.5 text-xs">
              <span className="text-text-secondary">{s.sector}</span>
              <span className="font-mono tabular-nums text-accent">{s.count}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function BigMovesBanner({ moves }: { moves: { type: string; message: string; value: number }[] }) {
  return (
    <div className="rounded-sm border border-warning/40 bg-warning/10 px-3 py-2">
      <div className="mb-1 flex items-center gap-2">
        <span className="label text-warning">big moves</span>
      </div>
      <ul className="space-y-1">
        {moves.map((m, i) => (
          <li key={i} className="flex items-center gap-2 text-sm text-text">
            <Tag variant={m.type === "day_move" ? "danger" : "warning"}>{m.type === "day_move" ? "price" : "cluster"}</Tag>
            <span>{m.message}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ConnectedNewsRow({ capture }: { capture: Capture }) {
  const tags = Array.isArray(capture.ai_tags) ? capture.ai_tags : []
  const text =
    capture.topic_tag ||
    capture.ocr_text?.slice(0, 120) ||
    capture.voice_transcript?.slice(0, 120) ||
    "(capture)"
  const when = capture.captured_at ? capture.captured_at.replace("T", " ").slice(0, 16) : ""
  return (
    <li className="rounded-sm border border-border/60 px-2.5 py-1.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm text-text">{text}</span>
        <span className="shrink-0 font-mono text-xs text-text-label">{when}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <span className={cn("text-[11px] uppercase tracking-wider",
          capture.type === "voice" ? "text-accent" : "text-text-label")}>{capture.type}</span>
        {tags.slice(0, 4).map((t, i) => (
          <span key={i} className="text-[11px] text-text-label">#{String(t)}</span>
        ))}
        {capture.status && capture.status !== "approved" && (
          <Tag variant={capture.status === "pending" ? "muted" : "accent"}>{capture.status}</Tag>
        )}
      </div>
    </li>
  )
}
