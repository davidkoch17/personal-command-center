import { createContext, useContext, type MouseEvent, type ReactNode } from "react"
import { Link } from "react-router-dom"
import { openInOs } from "@/lib/open-in-os"

/**
 * Renders a small, safe subset of inline Markdown found in vault text:
 *   **bold**   → <strong>
 *   *italic*   → <em>
 *   `code`     → <code>
 * Obsidian wikilinks ([[Target|Label]] / [[Target]], in tables [[Target\|Label]])
 * are stripped to their label — unless rendered inside a <WikilinkProvider>,
 * where they become clickable links (see :func:`WikiLink`).
 * Everything else is emitted as literal text — no block parsing, no HTML.
 *
 * Underscore-italics (_x_) are intentionally NOT supported, so snake_case names
 * like Task_Command_Center are never mangled into italics.
 */
const TOKEN =
  /(!?\[\[([^\]|\\]+?)(?:\\?\|([^\]]+))?\]\])|(\*\*([^*]+)\*\*)|(`([^`]+)`)|(\*([^*\s][^*]*?)\*)/

const WikilinkContext = createContext(false)

/** Turns Obsidian wikilinks inside any descendant <InlineMd> into clickable links. */
export function WikilinkProvider({ children }: { children: ReactNode }) {
  return <WikilinkContext.Provider value={true}>{children}</WikilinkContext.Provider>
}

const PROJECT_OVERVIEW = /^1 - Projects\/(\d+) - [^/]+\/_overview(?:\.md)?$/i

/**
 * One clickable wikilink. Target is a vault path (or bare note name):
 *   - another project's `_overview` → in-app /projects/<N>
 *   - no extension or `.md`         → obsidian://open (Obsidian assumes .md)
 *   - any other file                → POST /api/system/open (OS default app)
 * Clicks don't bubble, so a link inside a toggle row never ticks the row.
 */
function WikiLink({ target, label }: { target: string; label: string }) {
  const path = target.split(/[#^]/)[0].trim()
  const stop = (e: MouseEvent) => e.stopPropagation()
  const cls = "text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
  const project = path.match(PROJECT_OVERVIEW)
  if (project) {
    return (
      <Link to={`/projects/${Number(project[1])}`} onClick={stop} className={cls}>
        {label}
      </Link>
    )
  }
  const ext = path.match(/\.([a-z0-9]{1,6})$/i)?.[1]?.toLowerCase()
  if (!ext || ext === "md") {
    const href = `obsidian://open?vault=David_Work_OS&file=${encodeURIComponent(path)}`
    return (
      <a href={href} onClick={stop} className={cls} title={path}>
        {label}
      </a>
    )
  }
  return (
    <a
      href="#"
      title={path}
      className={cls}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void openInOs(path)
      }}
    >
      {label}
    </a>
  )
}

function parseInline(text: string, links: boolean): ReactNode[] {
  const out: ReactNode[] = []
  let rest = text
  let key = 0
  let m: RegExpMatchArray | null
  while ((m = rest.match(TOKEN)) && m.index !== undefined) {
    if (m.index > 0) out.push(rest.slice(0, m.index))
    if (m[2] !== undefined) {
      const target = m[2].trim()
      const label = (m[3] ?? target.split("/").pop() ?? target).trim()
      out.push(links ? <WikiLink key={key++} target={target} label={label} /> : label)
    } else if (m[5] !== undefined) {
      out.push(
        <strong key={key++} className="font-semibold text-text">
          {parseInline(m[5], links)}
        </strong>,
      )
    } else if (m[7] !== undefined) {
      out.push(
        <code key={key++} className="rounded bg-bg px-1 py-0.5 font-mono text-[0.85em]">
          {m[7]}
        </code>,
      )
    } else if (m[9] !== undefined) {
      out.push(<em key={key++}>{m[9]}</em>)
    }
    rest = rest.slice(m.index + m[0].length)
  }
  if (rest) out.push(rest)
  return out
}

export function InlineMd({ text }: { text: string | null | undefined }): ReactNode {
  const links = useContext(WikilinkContext)
  if (!text) return null
  return <>{parseInline(text, links)}</>
}
