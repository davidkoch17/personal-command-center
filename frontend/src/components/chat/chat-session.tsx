import { useCallback, useEffect, useRef, useState } from "react"
import {
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  Globe,
  Loader2,
  Maximize2,
  Minimize2,
  Save,
  Search,
  Send,
  Terminal,
  Wrench,
  X,
  Zap,
} from "lucide-react"
import { API_BASE } from "@/lib/api"
import { cn } from "@/lib/utils"
import { ChatMarkdown } from "@/components/chat/chat-markdown"

/**
 * One streaming, multi-turn Claude Code session over the ``/api/chat/stream``
 * WebSocket — extracted from the standalone ``/chat`` page (Item #4) so the
 * same surface powers both:
 *
 * - the full chat window (``pages/chat.tsx`` renders it at ``h-screen``), and
 * - the Home "Ask Claude" right-side overlay (``embedded`` + ``onClose``,
 *   optionally auto-sending an ``initialMessage`` once connected).
 *
 * Claude reads freely and streams its answer token-by-token; writes, shell
 * commands and skill-runs each surface an inline approval card that David
 * approves or declines before the action runs.
 */

type ConnState = "connecting" | "ready" | "streaming" | "closed" | "error"

interface ToolCall {
  id: string
  name: string
  input: Record<string, unknown>
  result?: string
  isError?: boolean
  /** Set while this action is awaiting David's approval. */
  requestId?: string
  /** Recorded once David has approved/declined. */
  decision?: "approved" | "denied"
}

interface ChatMsg {
  id: string
  role: "user" | "assistant"
  text: string
  thinking: string
  tools: ToolCall[]
  streaming: boolean
  error?: string
}

let msgSeq = 0
const newId = () => `m${msgSeq++}`

export function ChatSession({
  page = null,
  initialMessage,
  embedded = false,
  onClose,
}: {
  /** Dashboard path the session was opened from (context for the backend). */
  page?: string | null
  /** Auto-sent as the first user message once the socket is ready. */
  initialMessage?: string
  /** Embedded mode: fills its container (h-full) and hides window-only chrome. */
  embedded?: boolean
  /** Renders a close button in the header (used by the Home overlay). */
  onClose?: () => void
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState("")
  const [conn, setConn] = useState<ConnState>("connecting")
  const [sessionId, setSessionId] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const initialSentRef = useRef(false)

  // --- Update helpers — all mutate the *current* (last) assistant message. ---
  const patchLast = useCallback((fn: (m: ChatMsg) => ChatMsg) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev
      const out = prev.slice()
      const i = out.length - 1
      if (out[i].role !== "assistant") return prev
      out[i] = fn(out[i])
      return out
    })
  }, [])

  const connect = useCallback(() => {
    const params = new URLSearchParams()
    if (page) params.set("page", page)
    const qs = params.toString()
    const url = `${API_BASE.replace(/^http/, "ws")}/api/chat/stream${qs ? `?${qs}` : ""}`

    let ws: WebSocket
    try {
      ws = new WebSocket(url)
    } catch {
      setConn("error")
      return
    }
    wsRef.current = ws
    setConn("connecting")

    ws.onopen = () => setConn("ready")
    ws.onclose = () => setConn("closed")
    ws.onerror = () => setConn("error")
    ws.onmessage = (e) => {
      let msg: { type: string; [k: string]: unknown }
      try {
        msg = JSON.parse(e.data)
      } catch {
        return
      }
      switch (msg.type) {
        case "session":
          setSessionId(String(msg.session_id ?? ""))
          break
        case "text_delta":
          patchLast((m) => ({ ...m, text: m.text + String(msg.text ?? "") }))
          break
        case "thinking_delta":
          patchLast((m) => ({ ...m, thinking: m.thinking + String(msg.text ?? "") }))
          break
        case "tool_use": {
          const id = String(msg.id ?? "")
          const name = String(msg.name ?? "tool")
          const input = (msg.input as Record<string, unknown>) ?? {}
          patchLast((m) => {
            if (m.tools.some((t) => t.id === id)) {
              return { ...m, tools: m.tools.map((t) => (t.id === id ? { ...t, name, input } : t)) }
            }
            return { ...m, tools: [...m.tools, { id, name, input }] }
          })
          break
        }
        case "approval_request": {
          const rid = String(msg.request_id ?? "")
          const tuid = msg.tool_use_id ? String(msg.tool_use_id) : rid
          const name = String(msg.name ?? "tool")
          const input = (msg.input as Record<string, unknown>) ?? {}
          patchLast((m) => {
            if (m.tools.some((t) => t.id === tuid)) {
              return {
                ...m,
                tools: m.tools.map((t) =>
                  t.id === tuid ? { ...t, name, input, requestId: rid } : t,
                ),
              }
            }
            return { ...m, tools: [...m.tools, { id: tuid, name, input, requestId: rid }] }
          })
          break
        }
        case "tool_result":
          patchLast((m) => ({
            ...m,
            tools: m.tools.map((t) =>
              t.id === msg.tool_use_id
                ? { ...t, result: String(msg.content ?? ""), isError: Boolean(msg.is_error) }
                : t,
            ),
          }))
          break
        case "result":
          patchLast((m) => ({ ...m, streaming: false }))
          setConn("ready")
          break
        case "error":
          patchLast((m) => ({ ...m, streaming: false, error: String(msg.message ?? "error") }))
          setConn("ready")
          break
      }
    }
  }, [page, patchLast])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  // Auto-scroll to the tail on any change.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  const decide = useCallback((requestId: string, approve: boolean) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: approve ? "approve" : "deny", request_id: requestId }))
    }
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        tools: m.tools.map((t) =>
          t.requestId === requestId
            ? { ...t, requestId: undefined, decision: approve ? "approved" : "denied" }
            : t,
        ),
      })),
    )
  }, [])

  const sendText = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      const ws = wsRef.current
      if (!trimmed || !ws || ws.readyState !== WebSocket.OPEN) return
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: "user", text: trimmed, thinking: "", tools: [], streaming: false },
        { id: newId(), role: "assistant", text: "", thinking: "", tools: [], streaming: true },
      ])
      ws.send(JSON.stringify({ type: "user", text: trimmed }))
      setConn("streaming")
    },
    [],
  )

  // Auto-send the initial question once (Home "Ask Claude" overlay path).
  useEffect(() => {
    if (conn === "ready" && initialMessage && !initialSentRef.current) {
      initialSentRef.current = true
      sendText(initialMessage)
    }
  }, [conn, initialMessage, sendText])

  function send() {
    if (conn === "streaming") return
    sendText(input)
    setInput("")
  }

  return (
    <div className={cn("flex flex-col bg-bg text-text", embedded ? "h-full" : "h-screen")}>
      <ChatHeader
        conn={conn}
        sessionId={sessionId}
        page={page}
        embedded={embedded}
        onReconnect={connect}
        onClose={onClose}
      />

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
          {messages.length === 0 && <EmptyState page={page} />}
          {messages.map((m) => (
            <MessageRow key={m.id} msg={m} onDecision={decide} />
          ))}
        </div>
      </div>

      <Composer
        value={input}
        onChange={setInput}
        onSend={send}
        disabled={conn === "streaming" || conn === "connecting"}
      />
    </div>
  )
}

// --- Header -----------------------------------------------------------------
const CONN_LABEL: Record<ConnState, { text: string; dot: string }> = {
  connecting: { text: "connecting…", dot: "bg-warning" },
  ready: { text: "ready", dot: "bg-success" },
  streaming: { text: "thinking…", dot: "bg-accent animate-pulse" },
  closed: { text: "disconnected", dot: "bg-text-disabled" },
  error: { text: "connection error", dot: "bg-danger" },
}

function FullscreenToggle() {
  const [isFs, setIsFs] = useState(false)
  useEffect(() => {
    const onChange = () => setIsFs(Boolean(document.fullscreenElement))
    document.addEventListener("fullscreenchange", onChange)
    return () => document.removeEventListener("fullscreenchange", onChange)
  }, [])
  const toggle = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {})
    } else {
      document.documentElement.requestFullscreen().catch(() => {})
    }
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isFs ? "exit fullscreen" : "fullscreen"}
      title={isFs ? "exit fullscreen" : "fullscreen"}
      className="text-text-secondary hover:text-text"
    >
      {isFs ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
    </button>
  )
}

function ChatHeader({
  conn,
  sessionId,
  page,
  embedded,
  onReconnect,
  onClose,
}: {
  conn: ConnState
  sessionId: string | null
  page: string | null
  embedded: boolean
  onReconnect: () => void
  onClose?: () => void
}) {
  const s = CONN_LABEL[conn]
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-bg-panel px-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold tracking-tight lowercase">
          {embedded ? "ask claude" : "command center · chat"}
        </span>
        <span className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text-label">
          approve-to-write
        </span>
        {page && !embedded && (
          <span className="hidden font-mono text-[11px] text-text-label sm:inline">from {page}</span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {!embedded && <FullscreenToggle />}
        {sessionId && !embedded && (
          <span className="hidden font-mono text-[10px] text-text-disabled sm:inline">
            {sessionId.slice(0, 8)}
          </span>
        )}
        <span className="flex items-center gap-1.5 font-mono text-[11px] text-text-secondary">
          <span className={cn("h-1.5 w-1.5 rounded-full", s.dot)} />
          {s.text}
        </span>
        {(conn === "closed" || conn === "error") && (
          <button
            type="button"
            onClick={onReconnect}
            className="rounded-sm border border-border px-2 py-0.5 text-xs text-text-secondary hover:bg-bg-panel-hover hover:text-text"
          >
            reconnect
          </button>
        )}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="close chat"
            className="text-text-secondary hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </header>
  )
}

function EmptyState({ page }: { page: string | null }) {
  return (
    <div className="mt-24 text-center">
      <p className="text-lg font-semibold capitalize">talk to claude code</p>
      <p className="mt-1 text-sm text-text-secondary">
        ask anything about your vault, finances, projects, or this codebase.
        {page ? ` you're here from ${page}.` : ""}
      </p>
      <p className="mt-3 font-mono text-xs text-text-label">
        it can read freely; writes, commands &amp; skill-runs ask you first.
      </p>
    </div>
  )
}

// --- Messages ---------------------------------------------------------------
function MessageRow({
  msg,
  onDecision,
}: {
  msg: ChatMsg
  onDecision: (requestId: string, approve: boolean) => void
}) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg rounded-br-sm bg-accent-soft/40 px-4 py-2.5 text-[0.95rem] text-text">
          {msg.text}
        </div>
      </div>
    )
  }

  const idle = msg.streaming && !msg.text && !msg.thinking && msg.tools.length === 0
  return (
    <div className="flex flex-col gap-2">
      {msg.thinking && <ThinkingBlock text={msg.thinking} streaming={msg.streaming} />}
      {msg.tools.map((t) => (
        <ToolCard key={t.id} tool={t} onDecision={onDecision} />
      ))}
      {msg.text && <ChatMarkdown text={msg.text} />}
      {idle && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> thinking…
        </div>
      )}
      {msg.error && (
        <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {msg.error}
        </div>
      )}
    </div>
  )
}

function ThinkingBlock({ text, streaming }: { text: string; streaming: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-md border border-border bg-bg-panel/50">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider text-text-label"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        thinking{streaming ? "…" : ""}
      </button>
      {open && (
        <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap px-3 pb-2 font-mono text-[11px] leading-relaxed text-text-secondary">
          {text}
        </pre>
      )}
    </div>
  )
}

// --- Tool cards (reads run silently; writes/commands/skills ask first) ------
/** mcp__cc__vault_write → vault_write; built-ins pass through unchanged. */
function prettyName(name: string): string {
  const m = name.match(/^mcp__[^_]+__(.+)$/)
  return m ? m[1] : name
}

const EDIT_TOOLS = new Set(["Edit", "Write", "MultiEdit", "vault_write", "vault_append"])

function toolIcon(name: string) {
  const n = prettyName(name)
  if (n === "Read") return <FileText className="h-3.5 w-3.5" />
  if (n === "Grep" || n === "Glob") return <Search className="h-3.5 w-3.5" />
  if (n === "WebSearch" || n === "WebFetch") return <Globe className="h-3.5 w-3.5" />
  if (n === "Bash") return <Terminal className="h-3.5 w-3.5" />
  if (n === "run_skill") return <Zap className="h-3.5 w-3.5" />
  if (n === "vault_write" || n === "vault_append") return <Save className="h-3.5 w-3.5" />
  return <Wrench className="h-3.5 w-3.5" />
}

function toolSummary(t: ToolCall): string {
  const i = t.input
  const pick = (k: string) => (typeof i[k] === "string" ? (i[k] as string) : undefined)
  return (
    pick("file_path") ??
    pick("path") ??
    pick("command") ??
    pick("name") ??
    pick("pattern") ??
    pick("query") ??
    pick("url") ??
    ""
  )
}

function ToolCard({
  tool,
  onDecision,
}: {
  tool: ToolCall
  onDecision: (requestId: string, approve: boolean) => void
}) {
  const awaiting = Boolean(tool.requestId)
  const [open, setOpen] = useState(awaiting)
  const name = prettyName(tool.name)
  const isEdit = EDIT_TOOLS.has(name)

  return (
    <div
      className={cn(
        "rounded-md border text-sm",
        awaiting ? "border-accent/60 bg-accent-soft/10" : "border-border bg-bg-panel/60",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
      >
        <span className="text-text-secondary">{toolIcon(tool.name)}</span>
        <span className="font-mono text-xs text-text">{name}</span>
        <span className="flex-1 truncate font-mono text-xs text-text-label">{toolSummary(tool)}</span>
        {awaiting ? (
          <span className="text-[10px] font-medium uppercase tracking-wider text-accent">needs ok</span>
        ) : tool.decision === "denied" ? (
          <span className="text-[10px] text-danger">declined</span>
        ) : tool.result === undefined ? (
          <Loader2 className="h-3 w-3 animate-spin text-text-label" />
        ) : (
          <span className={cn("text-[10px]", tool.isError ? "text-danger" : "text-success")}>
            {tool.isError ? "error" : "done"}
          </span>
        )}
        {open ? (
          <ChevronDown className="h-3 w-3 text-text-label" />
        ) : (
          <ChevronRight className="h-3 w-3 text-text-label" />
        )}
      </button>

      {open && (
        <div className="border-t border-border px-3 py-2">
          <ToolPreview name={name} input={tool.input} />
          {!awaiting && tool.result !== undefined && (
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap border-t border-border pt-2 font-mono text-[11px] leading-relaxed text-text-secondary">
              {tool.result || "(no output)"}
            </pre>
          )}
        </div>
      )}

      {awaiting && tool.requestId && (
        <div className="flex items-center justify-end gap-2 border-t border-accent/30 px-3 py-2">
          <span className="mr-auto font-mono text-[11px] text-text-secondary">
            {isEdit ? "apply this change?" : name === "Bash" ? "run this command?" : "approve this action?"}
          </span>
          <button
            type="button"
            onClick={() => onDecision(tool.requestId as string, false)}
            className="flex items-center gap-1 rounded-sm border border-border px-2 py-1 text-xs text-text-secondary hover:bg-bg-panel-hover hover:text-text"
          >
            <X className="h-3 w-3" /> decline
          </button>
          <button
            type="button"
            onClick={() => onDecision(tool.requestId as string, true)}
            className="flex items-center gap-1 rounded-sm bg-accent px-2.5 py-1 text-xs text-white hover:bg-accent-dim"
          >
            <Check className="h-3 w-3" /> approve
          </button>
        </div>
      )}
    </div>
  )
}

/** Renders a tool's input the way it matters: diff for edits, command for Bash,
 *  args for a skill-run, raw JSON otherwise. */
function ToolPreview({ name, input }: { name: string; input: Record<string, unknown> }) {
  const str = (k: string) => (typeof input[k] === "string" ? (input[k] as string) : undefined)

  if (name === "Bash") {
    return (
      <pre className="overflow-x-auto rounded-sm bg-bg p-2 font-mono text-[11px] leading-relaxed text-text">
        $ {str("command") ?? ""}
      </pre>
    )
  }
  if (name === "run_skill") {
    return (
      <div className="font-mono text-[11px] text-text-secondary">
        <div>
          skill: <span className="text-text">{str("name")}</span>
        </div>
        {str("args_json") && str("args_json") !== "{}" && (
          <pre className="mt-1 overflow-x-auto rounded-sm bg-bg p-2">{str("args_json")}</pre>
        )}
      </div>
    )
  }
  if (EDIT_TOOLS.has(name)) {
    const path = str("file_path") ?? str("path")
    return (
      <div>
        {path && <div className="mb-1 font-mono text-[11px] text-text-label">{path}</div>}
        <DiffView input={input} />
      </div>
    )
  }
  return (
    <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-secondary">
      {JSON.stringify(input, null, 2)}
    </pre>
  )
}

/** Minimal old→new line diff for edit tool inputs (Edit/Write/vault_write). */
function DiffView({ input }: { input: Record<string, unknown> }) {
  const oldStr = typeof input.old_string === "string" ? input.old_string : ""
  const newStr =
    typeof input.new_string === "string"
      ? input.new_string
      : typeof input.content === "string"
        ? input.content
        : ""
  return (
    <pre className="max-h-64 overflow-auto rounded-sm bg-bg p-2 font-mono text-[11px] leading-relaxed">
      {oldStr.split("\n").map(
        (l, i) =>
          oldStr && (
            <div key={`o${i}`} className="text-danger">
              - {l}
            </div>
          ),
      )}
      {newStr.split("\n").map((l, i) => (
        <div key={`n${i}`} className="text-success">
          + {l}
        </div>
      ))}
    </pre>
  )
}

// --- Composer ---------------------------------------------------------------
function Composer({
  value,
  onChange,
  onSend,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  disabled: boolean
}) {
  return (
    <div className="shrink-0 border-t border-border bg-bg-panel px-4 py-3">
      <div className="mx-auto flex w-full max-w-3xl items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              onSend()
            }
          }}
          rows={1}
          placeholder="message claude…  (Enter to send, Shift+Enter for newline)"
          className="max-h-40 min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-bg px-3 py-2.5 text-sm text-text placeholder:text-text-label focus:border-accent focus:outline-none"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-dim disabled:opacity-40"
          aria-label="send"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
