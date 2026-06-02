import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useRecordTransaction, type TransactionRequest } from "@/hooks/useFinance"
import { isoDate } from "@/lib/utils"
import { toast } from "@/lib/toast-store"

const ACTIONS = ["buy", "sell", "dividend", "deposit", "withdraw", "split"] as const

/**
 * Log-transaction form (POST /api/finance/transactions). Used inline on the
 * Portfolio workspace and inside a dialog on the Home Quick Run panel.
 */
export function TransactionForm({ onDone }: { onDone?: () => void }) {
  const record = useRecordTransaction()
  const [ticker, setTicker] = useState("")
  const [action, setAction] = useState<(typeof ACTIONS)[number]>("buy")
  const [date, setDate] = useState(isoDate())
  const [quantity, setQuantity] = useState("")
  const [price, setPrice] = useState("")
  const [currency, setCurrency] = useState("EUR")
  const [fees, setFees] = useState("")
  const [notes, setNotes] = useState("")

  const valid = ticker.trim() && quantity.trim() && price.trim() && date

  function submit() {
    if (!valid) return
    const req: TransactionRequest = {
      date,
      ticker: ticker.trim().toUpperCase(),
      action,
      quantity: Number(quantity),
      price: Number(price),
      currency,
      fees: fees ? Number(fees) : 0,
      notes: notes.trim() || null,
    }
    record.mutate(req, {
      onSuccess: () => {
        toast.success("transaction logged", `${action} ${quantity} ${req.ticker}`)
        setTicker("")
        setQuantity("")
        setPrice("")
        setFees("")
        setNotes("")
        onDone?.()
      },
      onError: (e) => toast.error("could not log transaction", String(e)),
    })
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="ticker">
          <Input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="GOOGL" mono />
        </Field>
        <Field label="action">
          <Select value={action} onValueChange={(v) => setAction(v as typeof action)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACTIONS.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="date">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} mono />
        </Field>
        <Field label="quantity">
          <Input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="10"
            mono
          />
        </Field>
        <Field label="price">
          <Input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="420"
            mono
          />
        </Field>
        <Field label="currency">
          <Select value={currency} onValueChange={setCurrency}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["EUR", "USD", "GBP"].map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="fees (optional)">
          <Input
            type="number"
            value={fees}
            onChange={(e) => setFees(e.target.value)}
            placeholder="0"
            mono
          />
        </Field>
        <Field label="notes (optional)" className="col-span-2">
          <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="…" />
        </Field>
      </div>
      <div className="flex justify-end">
        <Button onClick={submit} disabled={!valid || record.isPending}>
          {record.isPending ? "logging…" : "log transaction"}
        </Button>
      </div>
    </div>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <div className="label mb-1">{label}</div>
      {children}
    </div>
  )
}
