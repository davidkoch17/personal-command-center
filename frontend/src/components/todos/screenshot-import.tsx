import { useEffect, useRef, useState } from "react"
import { ImagePlus, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tag } from "@/components/ui/tag"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useCreateTodos, useImportTodoImage, type TodoProposal } from "@/hooks/useTodos"
import { toast } from "@/lib/toast-store"

interface Row extends TodoProposal {
  keep: boolean
}

/** Read an image File/Blob as raw base64 (no data: prefix). */
function toBase64(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "")
    r.onerror = () => reject(r.error)
    r.readAsDataURL(file)
  })
}

/** First image in a clipboard / drop payload, if any. */
function imageFrom(items: DataTransferItemList | null | undefined): File | null {
  for (const item of Array.from(items ?? [])) {
    if (item.kind === "file" && item.type.startsWith("image/")) return item.getAsFile()
  }
  return null
}

/**
 * Screenshot → to-dos. Paste an image anywhere on the To-dos page (Ctrl+V, when
 * not typing in a field), drop it, or pick a file. Claude reads it and returns
 * proposals; nothing is saved until "add" — then all kept rows are written to
 * todos.json in one go.
 */
export function ScreenshotImport({ areas }: { areas: string[] }) {
  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [rows, setRows] = useState<Row[] | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const read = useImportTodoImage()
  const create = useCreateTodos()

  async function handleImage(file: File) {
    setOpen(true)
    setRows(null)
    setPreview(URL.createObjectURL(file))
    const image_base64 = await toBase64(file)
    read.mutate(
      { image_base64, mime: file.type || "image/png" },
      {
        onSuccess: (r) =>
          setRows(r.proposals.map((p) => ({ ...p, keep: !p.done_in_image }))),
      },
    )
  }

  // Page-wide paste: only when the user isn't typing into a field.
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const el = document.activeElement
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return
      const file = imageFrom(e.clipboardData?.items)
      if (!file) return
      e.preventDefault()
      void handleImage(file)
    }
    window.addEventListener("paste", onPaste)
    return () => window.removeEventListener("paste", onPaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function close() {
    setOpen(false)
    setRows(null)
    if (preview) URL.revokeObjectURL(preview)
    setPreview(null)
  }

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs && rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  const kept = rows?.filter((r) => r.keep && r.title.trim()) ?? []

  function save() {
    create.mutate(
      kept.map(({ title, area, priority, due, subtasks }) => ({
        title: title.trim(),
        area,
        priority,
        due,
        subtasks,
      })),
      {
        onSuccess: () => {
          toast.success(`${kept.length} to-do${kept.length === 1 ? "" : "s"} added`)
          close()
        },
      },
    )
  }

  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => fileRef.current?.click()}
        title="or just paste a screenshot (Ctrl+V) anywhere on this page"
      >
        <ImagePlus className="h-3.5 w-3.5" /> from screenshot
      </Button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void handleImage(f)
          e.target.value = ""
        }}
      />

      <Dialog open={open} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>to-dos from screenshot</DialogTitle>
            <DialogDescription>
              Claude reads the image. Check the list, untick what you don't want, then add.
            </DialogDescription>
          </DialogHeader>

          {preview && (
            <img
              src={preview}
              alt="pasted screenshot"
              className="mb-3 max-h-48 w-full rounded border border-border object-contain"
            />
          )}

          {read.isPending && (
            <div className="flex items-center gap-2 py-4 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" /> reading the screenshot… (10–40 s)
            </div>
          )}
          {read.isError && (
            <p className="py-2 text-sm text-danger">Couldn't read it. Try a clearer screenshot.</p>
          )}
          {rows && rows.length === 0 && (
            <p className="py-2 text-sm text-text-secondary">No to-dos found in this image.</p>
          )}

          {rows && rows.length > 0 && (
            <ul className="divide-y divide-border">
              {rows.map((r, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 py-2">
                  <input
                    type="checkbox"
                    checked={r.keep}
                    onChange={(e) => setRow(i, { keep: e.target.checked })}
                    className="h-4 w-4 accent-[rgb(var(--color-accent))]"
                    aria-label="keep"
                  />
                  <Input
                    value={r.title}
                    onChange={(e) => setRow(i, { title: e.target.value })}
                    className="h-8 min-w-[12rem] flex-1"
                  />
                  <div className="w-32">
                    <Select value={r.area} onValueChange={(v) => setRow(i, { area: v })}>
                      <SelectTrigger className="h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {areas.map((a) => (
                          <SelectItem key={a} value={a}>
                            {a}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Input
                    type="date"
                    mono
                    value={r.due ?? ""}
                    onChange={(e) => setRow(i, { due: e.target.value || null })}
                    className="h-8 w-36"
                    aria-label="due date"
                  />
                  {r.subtasks.length > 0 && <Tag>{r.subtasks.length} subtasks</Tag>}
                  {r.done_in_image && <Tag variant="success">ticked in image</Tag>}
                </li>
              ))}
            </ul>
          )}

          <DialogFooter>
            <Button variant="secondary" onClick={close}>
              cancel
            </Button>
            <Button onClick={save} disabled={kept.length === 0 || create.isPending}>
              add {kept.length || ""}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
