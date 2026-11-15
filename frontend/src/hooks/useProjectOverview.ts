import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

/**
 * Project overviews — every project folder's `_overview.md`, parsed by the
 * backend (`modules/projects/overview.py`). The dashboard only reads them and
 * makes two surgical writes: tick a checkbox, append an update line.
 */

export type OverviewStatus = "active" | "waiting" | "paused" | "done"

export interface ActivityEntry {
  date_raw: string
  date: string | null
  text: string
}

export interface ProjectOverviewCard {
  id: string
  name: string
  folder: string
  status: OverviewStatus | null
  next_action: string | null
  updated: string | null
  review_by: string | null
  open_count: number
  waiting_count: number
  last_activity: ActivityEntry | null
  last_file_change: string | null
  last_touch: string | null
  stale: boolean
  review_due: boolean
  exists: boolean
}

export interface OpenItem {
  index: number
  line: number
  text: string
  checked: boolean
  waiting: boolean
  group: string | null
  group_note: string
}

export interface FilesTableRow {
  cells: string[]
  path: string | null
  vault_path: string | null
  is_dir: boolean
}

export interface RecentFile {
  rel_path: string
  name: string
  modified: string
  size: number
  path: string
  vault_path: string | null
}

export interface ProjectOverview {
  id: string
  name: string
  folder: string
  exists: boolean
  project: string | null
  status: OverviewStatus | null
  updated: string | null
  next_action: string | null
  review_by: string | null
  intro: { quote: string[]; nav: string[] }
  status_section: { markdown: string; current: string | null; next_action: string | null }
  open: OpenItem[]
  activity: ActivityEntry[]
  notes_md: string
  files_table: { headers: string[]; rows: FilesTableRow[]; extra: string }
  updates: string[]
  titles: Record<string, string>
  overview_path: string
  overview_vault_path: string | null
  recent_files: RecentFile[]
}

export function useProjectOverviews() {
  return useQuery({
    queryKey: ["project-overviews"],
    queryFn: () => api.get<ProjectOverviewCard[]>("/api/projects"),
  })
}

export function useProjectOverview(id: string | undefined) {
  return useQuery({
    queryKey: ["project-overview", id],
    queryFn: () => api.get<ProjectOverview>(`/api/projects/${id}`),
    enabled: !!id,
  })
}

function useInvalidate(id: string | undefined) {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ["project-overview", id] })
    qc.invalidateQueries({ queryKey: ["project-overviews"] })
  }
}

/** Flip one ✅ checkbox. Sends index + text so a concurrent edit can't tick the wrong line. */
export function useToggleOverviewItem(id: string | undefined) {
  const invalidate = useInvalidate(id)
  return useMutation({
    mutationFn: (item: Pick<OpenItem, "index" | "text">) =>
      api.post<{ ok: boolean; checked: boolean }>(`/api/projects/${id}/toggle`, item),
    onSettled: invalidate,
  })
}

/** Append `- DD.MM. HH:MM – text` to the 💬 Updates inbox. */
export function useAppendOverviewUpdate(id: string | undefined) {
  const invalidate = useInvalidate(id)
  return useMutation({
    mutationFn: (text: string) =>
      api.post<{ ok: boolean; line: string }>(`/api/projects/${id}/update`, { text }),
    onSuccess: invalidate,
  })
}

/** `obsidian://` deep link for a vault-relative path. */
export function obsidianUrl(vaultPath: string): string {
  return `obsidian://open?vault=David_Work_OS&file=${encodeURIComponent(vaultPath)}`
}

/** "2026-11-15" → "15.11." */
export function ddmm(iso: string | null | undefined): string {
  if (!iso) return "—"
  const [, m, d] = iso.slice(0, 10).split("-")
  return d && m ? `${d}.${m}.` : iso
}
