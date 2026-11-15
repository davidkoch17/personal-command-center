import { useMemo, useState, type ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { ExternalLink, File, FileText, Folder, Hourglass, Inbox, Send } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { TaskCheck } from "@/components/ui/task-check"
import { InlineMd, WikilinkProvider } from "@/components/ui/inline-markdown"
import { ChatMarkdown } from "@/components/chat/chat-markdown"
import { AttentionBadges, OverviewStatusTag } from "@/components/projects/overview-bits"
import {
  ddmm,
  obsidianUrl,
  useAppendOverviewUpdate,
  useProjectOverview,
  useToggleOverviewItem,
  type OpenItem,
  type ProjectOverview as Overview,
  type RecentFile,
} from "@/hooks/useProjectOverview"
import { openInOs } from "@/lib/open-in-os"
import { toast } from "@/lib/toast-store"
import { cn } from "@/lib/utils"

/**
 * One project's overview page, rendered from its `_overview.md`.
 * Only two writes happen here: ticking a ✅ item and appending an update line.
 */
export function ProjectOverview() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, isError, error } = useProjectOverview(id)

  return (
    <div className="space-y-5">
      <Link to="/projects" className="font-mono text-xs text-text-secondary hover:text-accent">
        ← projects
      </Link>

      {isError && (
        <Panel title="error" statusDotColor="danger">
          <p className="text-text-secondary">could not load project {id}: {String(error)}</p>
        </Panel>
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      )}

      {data && id && <OverviewBody id={id} ov={data} />}
    </div>
  )
}

function OverviewBody({ id, ov }: { id: string; ov: Overview }) {
  const today = new Date().toISOString().slice(0, 10)
  const reviewDue = !!ov.review_by && ov.review_by <= today
  const lastTouch = [ov.activity[0]?.date, ov.recent_files[0]?.modified.slice(0, 10)]
    .filter((d): d is string => !!d)
    .sort()
    .pop()
  const stale = !lastTouch || Date.parse(today) - Date.parse(lastTouch) > 21 * 864e5
  const next = ov.next_action || ov.status_section.next_action

  // Obsidian [[wikilinks]] anywhere on this page become clickable.
  return (
    <WikilinkProvider>
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <h1 className="page-title normal-case">{ov.name}</h1>
          <div className="flex flex-wrap items-center gap-1.5">
            <OverviewStatusTag status={ov.status} />
            <AttentionBadges card={{ stale, review_due: reviewDue, review_by: ov.review_by }} />
            <span className="font-mono text-[11px] text-text-label">
              updated {ddmm(ov.updated)} · review {ddmm(ov.review_by)}
            </span>
          </div>
        </div>
        {ov.overview_vault_path && (
          <Button asChild variant="secondary" size="sm">
            <a href={obsidianUrl(ov.overview_vault_path)}>
              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
              In Obsidian öffnen
            </a>
          </Button>
        )}
      </div>

      {!ov.exists && (
        <Panel title="kein _overview.md" statusDotColor="warning">
          <p className="text-sm text-text-secondary">
            In <code className="font-mono">{ov.folder}</code> liegt noch keine <code className="font-mono">_overview.md</code>.
          </p>
        </Panel>
      )}

      {/* Status + next action */}
      <Panel title={ov.titles.status?.replace(/^🧭\s*/, "").toLowerCase() || "status"} statusDotColor="accent">
        {next && (
          <div className="mb-3 rounded-sm border border-accent-dim/40 bg-accent-soft px-3 py-2 text-sm text-text">
            <span className="label mr-2">nächste aktion</span>
            <InlineMd text={next} />
          </div>
        )}
        {ov.status_section.current ? (
          <p className="text-sm text-text-secondary">
            <InlineMd text={ov.status_section.current} />
          </p>
        ) : ov.status_section.markdown ? (
          <div className="text-sm text-text-secondary">
            <ChatMarkdown text={ov.status_section.markdown} />
          </div>
        ) : (
          <EmptyState message="kein Status eingetragen" />
        )}
      </Panel>

      {/* Open items */}
      <OpenItems id={id} items={ov.open} />

      {/* Activity + recent files */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="letzte aktivität" meta={ov.activity.length ? `${ov.activity.length}` : undefined}>
          {ov.activity.length === 0 ? (
            <EmptyState message="keine Aktivität eingetragen" />
          ) : (
            <ol className="relative space-y-3 border-l border-border pl-4">
              {ov.activity.map((a, i) => (
                <li key={i} className="relative text-sm">
                  <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-accent" />
                  <span className="mr-2 font-mono text-xs text-text-label">{a.date_raw || "—"}</span>
                  <span className="text-text-secondary">
                    <InlineMd text={a.text} />
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Panel>
        <Panel title="zuletzt geänderte dateien" meta={`${ov.recent_files.length}`}>
          {ov.recent_files.length === 0 ? (
            <EmptyState icon={File} message="keine Dateien im Projektordner" />
          ) : (
            <ul className="space-y-0.5">
              {ov.recent_files.map((f) => (
                <li key={f.rel_path}>
                  <RecentFileRow file={f} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {/* Notes & decisions */}
      <Panel title={ov.titles.notes?.replace(/^📝\s*/, "").toLowerCase() || "notizen & entscheidungen"}>
        {ov.notes_md ? (
          <div className="text-sm text-text-secondary">
            <ChatMarkdown text={ov.notes_md} />
          </div>
        ) : (
          <EmptyState message="keine Notizen" />
        )}
      </Panel>

      {/* Where things live */}
      <WhereTable ov={ov} />

      {/* Updates inbox */}
      <UpdatesBox id={id} updates={ov.updates} />
    </WikilinkProvider>
  )
}

// --- open items ---------------------------------------------------------------
function OpenItems({ id, items }: { id: string; items: OpenItem[] }) {
  const toggle = useToggleOverviewItem(id)
  const groups = useMemo(() => {
    const out: { name: string | null; note: string; items: OpenItem[] }[] = []
    for (const it of items) {
      const last = out[out.length - 1]
      if (last && last.name === it.group) last.items.push(it)
      else out.push({ name: it.group, note: it.group_note, items: [it] })
    }
    return out
  }, [items])
  const open = items.filter((i) => !i.checked)
  const waiting = open.filter((i) => i.waiting).length

  function flip(it: OpenItem) {
    toggle.mutate(
      { index: it.index, text: it.text },
      {
        onSuccess: (r) => toast.show(r.checked ? "abgehakt" : "wieder offen", { detail: it.text }),
        onError: (e) => toast.error("konnte nicht speichern", String(e)),
      },
    )
  }

  return (
    <Panel
      title="offen"
      statusDotColor={open.length ? "warning" : "success"}
      meta={`${open.length - waiting} offen · ${waiting} wartet`}
    >
      {items.length === 0 ? (
        <EmptyState message="keine offenen Punkte" />
      ) : (
        <div className="space-y-4">
          {groups.map((g, gi) => (
            <div key={gi} className="space-y-1">
              {g.name && (
                <div className="text-xs font-semibold text-text">
                  <InlineMd text={g.name} />
                  {g.note && (
                    <span className="ml-2 font-normal text-text-label">
                      <InlineMd text={g.note} />
                    </span>
                  )}
                </div>
              )}
              {g.items.map((it) => (
                <TaskCheck
                  key={`${it.index}-${it.text}`}
                  checked={it.checked}
                  onToggle={() => flip(it)}
                  disabled={toggle.isPending}
                >
                  <span className="inline-flex flex-wrap items-baseline gap-1.5">
                    {it.waiting && !it.checked && (
                      <Hourglass className="h-3 w-3 shrink-0 self-center text-warning" aria-label="wartet" />
                    )}
                    <InlineMd text={it.text.replace(/⏳\s*/, "")} />
                  </span>
                </TaskCheck>
              ))}
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

// --- files --------------------------------------------------------------------
/** Opens .md files in Obsidian, everything else via the OS. */
function FileLink({
  path,
  vaultPath,
  isDir = false,
  className,
  children,
}: {
  path: string
  vaultPath: string | null
  isDir?: boolean
  className?: string
  children: ReactNode
}) {
  const cls = cn("text-left hover:text-accent transition-colors", className)
  if (!isDir && vaultPath && path.toLowerCase().endsWith(".md")) {
    return (
      <a href={obsidianUrl(vaultPath)} className={cls}>
        {children}
      </a>
    )
  }
  return (
    <button type="button" onClick={() => openInOs(path)} className={cls}>
      {children}
    </button>
  )
}

function fmtModified(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, "0")
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}. ${p(d.getHours())}:${p(d.getMinutes())}`
}

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 ** 2).toFixed(1)} MB`
}

function RecentFileRow({ file }: { file: RecentFile }) {
  const isMd = file.name.toLowerCase().endsWith(".md")
  const Icon = isMd ? FileText : File
  const dir = file.rel_path.includes("/") ? file.rel_path.slice(0, file.rel_path.lastIndexOf("/")) : ""
  return (
    <FileLink
      path={file.path}
      vaultPath={file.vault_path}
      className="flex w-full items-start gap-2 rounded-sm px-1.5 py-1 hover:bg-bg-panel-hover"
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-label" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm text-text">{file.name}</span>
        {dir && <span className="block truncate font-mono text-[10px] text-text-label">{dir}</span>}
      </span>
      <span className="shrink-0 text-right font-mono text-[10px] leading-4 text-text-label">
        {fmtModified(file.modified)}
        <br />
        {fmtSize(file.size)}
      </span>
    </FileLink>
  )
}

function WhereTable({ ov }: { ov: Overview }) {
  const { headers, rows, extra } = ov.files_table
  return (
    <Panel title={ov.titles.files?.replace(/^📂\s*/, "").toLowerCase() || "wo liegt was"}>
      {rows.length === 0 ? (
        <EmptyState icon={Folder} message="keine Tabelle eingetragen" />
      ) : (
        <div className="-mx-1 overflow-x-auto">
          <table className="w-full text-sm">
            {headers.length > 0 && (
              <thead>
                <tr className="border-b border-border text-left">
                  {headers.map((h, i) => (
                    <th key={i} className="label px-1 pb-1.5 font-normal">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-border/50 align-top last:border-0">
                  {r.cells.map((c, ci) => (
                    <td key={ci} className={cn("px-1 py-1.5", ci === 0 ? "whitespace-nowrap text-text" : "text-text-secondary")}>
                      {ci === 0 && r.path ? (
                        <FileLink path={r.path} vaultPath={r.vault_path} isDir={r.is_dir} className="inline-flex items-center gap-1.5">
                          {r.is_dir ? <Folder className="h-3.5 w-3.5 text-text-label" /> : <FileText className="h-3.5 w-3.5 text-text-label" />}
                          <InlineMd text={c.replace(/`/g, "")} />
                        </FileLink>
                      ) : (
                        <InlineMd text={c} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {extra && (
        <div className="mt-2 text-xs text-text-label">
          <ChatMarkdown text={extra} />
        </div>
      )}
    </Panel>
  )
}

// --- updates inbox ----------------------------------------------------------------
function UpdatesBox({ id, updates }: { id: string; updates: string[] }) {
  const [text, setText] = useState("")
  const append = useAppendOverviewUpdate(id)

  function send() {
    const t = text.trim()
    if (!t) return
    append.mutate(t, {
      onSuccess: () => {
        setText("")
        toast.success("update gespeichert", "Claude arbeitet es bei der nächsten Session ein.")
      },
      onError: (e) => toast.error("konnte nicht speichern", String(e)),
    })
  }

  return (
    <Panel title="updates" statusDotColor={updates.length ? "accent" : "muted"} meta={updates.length ? `${updates.length} offen` : undefined}>
      <div className="space-y-2">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send()
          }}
          placeholder="z. B. „Payroll angerufen, warte auf Rückmeldung“ (Strg+Enter)"
          rows={2}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-text-label">
            landet unter 💬 Updates in _overview.md · Claude arbeitet es ein
          </span>
          <Button size="sm" onClick={send} disabled={!text.trim() || append.isPending}>
            <Send className="mr-1.5 h-3.5 w-3.5" />
            senden
          </Button>
        </div>
      </div>
      <div className="mt-4">
        <div className="label mb-1.5">noch nicht eingearbeitet</div>
        {updates.length === 0 ? (
          <EmptyState icon={Inbox} message="nichts im Eingangskorb" />
        ) : (
          <ul className="space-y-1 text-sm text-text-secondary">
            {updates.map((u, i) => (
              <li key={i}>
                <InlineMd text={u.replace(/^[-*]\s+/, "")} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  )
}
