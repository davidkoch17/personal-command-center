import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

/**
 * Inline error panel with a retry action. Pair with the global query-error toast
 * (a request failure shows a toast AND this panel so the page never goes blank).
 */
export function ErrorState({
  message = "could not load this data. is the backend running on :8000?",
  onRetry,
}: ErrorStateProps) {
  return (
    <Panel title="error" statusDotColor="danger">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">{message}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            retry
          </Button>
        )}
      </div>
    </Panel>
  )
}
