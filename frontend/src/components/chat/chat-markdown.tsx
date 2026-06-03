import { Fragment, type ReactNode } from "react"
import { InlineMd } from "@/components/ui/inline-markdown"

/**
 * A small block-level Markdown renderer for the chat window. Deliberately
 * dependency-free (no react-markdown): it handles the blocks Claude actually
 * emits in chat — fenced code blocks, headings, bullet/numbered lists, and
 * paragraphs — and delegates inline spans (**bold**, `code`, *italic*) to the
 * shared :func:`InlineMd`. Anything fancier degrades to plain paragraphs, which
 * is fine for a chat transcript.
 */

type Block =
  | { kind: "code"; lang: string; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "p"; text: string }

function parseBlocks(src: string): Block[] {
  const lines = src.replace(/\r\n/g, "\n").split("\n")
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block.
    const fence = line.match(/^```(\w*)\s*$/)
    if (fence) {
      const lang = fence[1] || ""
      const buf: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i])) {
        buf.push(lines[i])
        i++
      }
      i++ // skip closing fence (or EOF)
      blocks.push({ kind: "code", lang, text: buf.join("\n") })
      continue
    }

    // Blank line — separator.
    if (line.trim() === "") {
      i++
      continue
    }

    // Heading.
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] })
      i++
      continue
    }

    // Unordered list run.
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""))
        i++
      }
      blocks.push({ kind: "ul", items })
      continue
    }

    // Ordered list run.
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""))
        i++
      }
      blocks.push({ kind: "ol", items })
      continue
    }

    // Paragraph — gather consecutive non-blank, non-special lines.
    const buf: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^```/.test(lines[i]) &&
      !/^#{1,6}\s/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      buf.push(lines[i])
      i++
    }
    blocks.push({ kind: "p", text: buf.join("\n") })
  }

  return blocks
}

const HEADING_CLASS: Record<number, string> = {
  1: "text-lg font-semibold",
  2: "text-base font-semibold",
  3: "text-sm font-semibold",
}

export function ChatMarkdown({ text }: { text: string }) {
  const blocks = parseBlocks(text)
  return (
    <div className="space-y-3 text-[0.95rem] leading-relaxed text-text">
      {blocks.map((b, idx) => {
        switch (b.kind) {
          case "code":
            return (
              <pre
                key={idx}
                className="overflow-x-auto rounded-md border border-border bg-bg p-3 font-mono text-[0.8rem] leading-relaxed text-text-secondary"
              >
                <code>{b.text}</code>
              </pre>
            )
          case "heading":
            return (
              <p key={idx} className={HEADING_CLASS[b.level] ?? "text-sm font-semibold"}>
                <InlineMd text={b.text} />
              </p>
            )
          case "ul":
            return (
              <ul key={idx} className="list-disc space-y-1 pl-5">
                {b.items.map((it, j) => (
                  <li key={j}>
                    <InlineMd text={it} />
                  </li>
                ))}
              </ul>
            )
          case "ol":
            return (
              <ol key={idx} className="list-decimal space-y-1 pl-5">
                {b.items.map((it, j) => (
                  <li key={j}>
                    <InlineMd text={it} />
                  </li>
                ))}
              </ol>
            )
          default:
            return (
              <p key={idx} className="whitespace-pre-wrap">
                {b.text.split("\n").map((ln, j) => (
                  <Fragment key={j}>
                    {j > 0 && <br />}
                    <InlineMd text={ln} />
                  </Fragment>
                ))}
              </p>
            ) as ReactNode
        }
      })}
    </div>
  )
}
