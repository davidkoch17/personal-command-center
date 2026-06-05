import { useNavigate } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Skeleton } from "@/components/ui/skeleton"
import { NumberDisplay } from "@/components/ui/number-display"
import { usePortfolioSnapshot } from "@/hooks/useFinance"

/**
 * STATE §2a — portfolio top-line: total value + deployable cash.
 * Click-through to the Portfolio overview page.
 */
export function PortfolioTopLine() {
  const { data, isLoading } = usePortfolioSnapshot()
  const navigate = useNavigate()

  return (
    <Panel title="portfolio" meta={`${data?.position_count ?? 0} positions`} statusDotColor="accent">
      {isLoading ? (
        <Skeleton className="h-16" />
      ) : (
        <button
          type="button"
          onClick={() => navigate("/portfolio")}
          className="block w-full rounded-sm text-left hover:bg-bg-panel-hover"
        >
          <NumberDisplay
            value={data?.total_value}
            format="currency"
            emphasized
            className="text-2xl"
          />
          <div className="mt-1 text-xs text-text-secondary">
            cash deployable{" "}
            <NumberDisplay value={data?.cash_deployable} format="currency" className="text-xs" />
          </div>
        </button>
      )}
    </Panel>
  )
}
