import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface ReadingBuckets {
  to_read: string[]
  reading_now: string[]
  done: string[]
}

export function useReading() {
  return useQuery({
    queryKey: ["reading"],
    queryFn: () => api.get<ReadingBuckets>("/api/reading"),
  })
}

/**
 * Split a reading bullet like `**Title** — Author (added ...)` into title +
 * author. Strips markdown bold; tolerates en/em dash or hyphen separators.
 */
export function parseBook(raw: string): { title: string; author: string } {
  const clean = raw.replace(/\*\*/g, "").trim()
  const m = clean.match(/^(.*?)\s[—–-]\s(.*)$/)
  if (m) return { title: m[1].trim(), author: m[2].trim() }
  return { title: clean, author: "" }
}
