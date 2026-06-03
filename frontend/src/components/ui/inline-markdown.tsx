import { type ReactNode } from "react"

/**
 * Renders a small, safe subset of inline Markdown found in vault text:
 *   **bold**   → <strong>
 *   *italic*   → <em>
 *   `code`     → <code>
 * Obsidian wikilinks ([[Target|Label]] / [[Target]]) are stripped to their
 * label. Everything else is emitted as literal text — no block parsing, no HTML.
 *
 * Underscore-italics (_x_) are intentionally NOT supported, so snake_case names
 * like Task_Command_Center are never mangled into italics.
 */
const TOKEN = /(\*\*([^*]+)\*\*)|(`([^`]+)`)|(\*([^*\s][^*]*?)\*)/

function parseInline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  let rest = text
  let key = 0
  let m: RegExpMatchArray | null
  while ((m = rest.match(TOKEN)) && m.index !== undefined) {
    if (m.index > 0) out.push(rest.slice(0, m.index))
    if (m[2] !== undefined) {
      out.push(
        <strong key={key++} className="font-semibold text-text">
          {m[2]}
        </strong>,
      )
    } else if (m[4] !== undefined) {
      out.push(
        <code key={key++} className="rounded bg-bg px-1 py-0.5 font-mono text-[0.85em]">
          {m[4]}
        </code>,
      )
    } else if (m[6] !== undefined) {
      out.push(<em key={key++}>{m[6]}</em>)
    }
    rest = rest.slice(m.index + m[0].length)
  }
  if (rest) out.push(rest)
  return out
}

export function InlineMd({ text }: { text: string | null | undefined }): ReactNode {
  if (!text) return null
  // Strip wikilink brackets, keeping the human label (right side of a pipe).
  const cleaned = text.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, a, b) => b || a)
  return <>{parseInline(cleaned)}</>
}
