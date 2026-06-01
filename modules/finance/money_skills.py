"""Claude-powered Money workspace skills (Phase 9b).

Cash-flow forecasting, the tax-scenario workshop, expense optimization, reviews,
deductible scans, and bill forecasting. All run via ``claude -p`` (zero API cost)
and work foreground or background. The tax scenario persists a dated Markdown
analysis to a chosen project folder (Immos, Personal_Brand, …) or the generic
Steuern scenarios folder.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from core.config import STEUERN_SCENARIOS_PATH, VAULT_PATH, get_logger
from modules.agents.claude_cli import run_claude
from modules.finance import money

logger = get_logger(__name__)


def _money_context() -> str:
    """Compact text snapshot of cash / income / spending for prompt context."""
    parts: list[str] = []
    try:
        cash = money.current_cash_balance()
        fixed = money.monthly_fixed_estimate()
        nw = money.latest_net_worth()
        runway = money.runway_months(cash, fixed)
        parts.append(
            f"Cash: €{cash or 0:,.0f} · Monthly fixed (est): €{fixed or 0:,.0f} · "
            f"Net worth: €{(nw.get('total') or 0):,.0f} · "
            f"Runway: {('%.1f mo' % runway) if runway else '—'}"
        )
    except Exception as exc:  # noqa: BLE001
        parts.append(f"(metrics unavailable: {exc})")
    try:
        totals = money.monthly_totals()
        if not totals.empty:
            parts.append("Monthly income/expenses (recent):\n" +
                         totals.sort_values("month").tail(6).to_string(index=False))
    except Exception:  # noqa: BLE001
        pass
    try:
        pivot = money.monthly_spending_by_category()
        if not pivot.empty:
            parts.append("Spending by category (last month):\n" +
                         pivot.tail(1).T.to_string())
    except Exception:  # noqa: BLE001
        pass
    return "\n\n".join(parts)


def _recent_transactions_text(months: int = 3) -> str:
    try:
        tx = money.transactions_normalized()
        if tx.empty:
            return "(no transactions)"
        tx = tx.sort_values("Date", ascending=False)
        cols = [c for c in ["Date", "Description", "Amount (€)", "Category", "Card"] if c in tx.columns]
        return tx[cols].head(120).to_string(index=False)
    except Exception as exc:  # noqa: BLE001
        return f"(transactions unavailable: {exc})"


def forecast_cash_flow(scenario_description: str = "") -> str:
    """Project 6/12-month cash flow from current burn + known income/expenses."""
    prompt = f"""You are David's CFO projecting personal cash flow.

# Current state
{_money_context()}

# Known future facts
- Evercore employment income starts 2026-07-01 (base + possible bonus).
- FFM rent and known recurring expenses continue.

# Scenario / assumptions from David
{scenario_description or '(use current run-rate; no extra assumptions)'}

Task (Markdown):
1. Assumptions table (income, expenses, one-offs)
2. Month-by-month projection for the next 6 and 12 months (cash balance path)
3. Runway / savings-rate read
4. Scenario sensitivity (best / base / worst)
5. Bottom line + the one variable that matters most
Show the arithmetic.
"""
    return run_claude(prompt, timeout=600)


def _slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_")
    return (s[:maxlen] or "scenario").lower()


def _resolve_save_dir(save_to_project: str | None) -> Path:
    """Resolve the target directory for a saved scenario.

    ``save_to_project`` may be absolute or vault-relative (e.g.
    ``1_Projects/06_Immos/Scenarios``). Falls back to the generic Steuern folder.
    """
    if save_to_project:
        p = Path(save_to_project)
        if not p.is_absolute():
            p = VAULT_PATH / save_to_project
        return p
    return STEUERN_SCENARIOS_PATH


def tax_scenario(scenario_description: str, save_to_project: str | None = None) -> Path:
    """Run a German-tax scenario analysis and save a dated Markdown file.

    Calls ``claude -p`` with the scenario + an instruction to consult current
    German tax law via web search. Saves to ``<save_to_project>/`` if given, else
    ``2_Personal/03_Steuern/Scenarios/``. Returns the written file path.
    """
    prompt = f"""You are a German tax-aware financial advisor (NOT a Steuerberater — flag where one is needed).

# David's current financial state
{_money_context()}

# Hypothetical to analyze
{scenario_description}

Use web search to ground every claim in CURRENT German tax law (2026). Produce a Markdown analysis:
1. Restated assumptions (make implicit numbers explicit)
2. Relevant tax law, each point with a citation
3. Year-by-year tax effect (table)
4. Net cost / benefit after tax
5. Comparison to an alternative use of the same capital
6. "Consult Steuerberater for X" flags
7. Bottom line in 2-3 lines
Be concrete with €. Cite everything.
"""
    analysis = run_claude(prompt, timeout=900)

    save_dir = _resolve_save_dir(save_to_project)
    save_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    topic = _slugify(scenario_description.splitlines()[0] if scenario_description else "scenario")
    out_path = save_dir / f"{stamp}_{topic}.md"
    header = f"# Tax scenario — {stamp}\n\n**Prompt:** {scenario_description.strip()}\n\n---\n\n"
    out_path.write_text(header + analysis, encoding="utf-8")
    return out_path


def find_expense_optimizations() -> str:
    """Review ~3 months of transactions for subscriptions / creep / waste."""
    prompt = f"""You are a frugal-but-smart financial reviewer scanning David's recent spending for savings.

# Recent transactions
{_recent_transactions_text(3)}

Task (Markdown):
1. Recurring subscriptions detected (with monthly €)
2. Category creep — categories trending up
3. Likely waste / duplicate services
4. Concrete cuts ranked by € saved/month, with the trade-off of each
5. Total potential monthly saving
Be specific; reference actual merchants/categories.
"""
    return run_claude(prompt, timeout=600)


def quarterly_money_review() -> str:
    """Generate a written quarterly money review document."""
    prompt = f"""Write David's quarterly money review.

# State + recent flows
{_money_context()}

# Recent transactions
{_recent_transactions_text(3)}

Task (Markdown):
1. Executive summary
2. Income vs expenses & savings rate trend
3. Category highlights & anomalies
4. Net worth trajectory
5. Recommendations for next quarter
6. Watch-items
"""
    return run_claude(prompt, timeout=900)


def tax_deductible_review() -> str:
    """Scan the last quarter for likely tax-deductible items (German context)."""
    prompt = f"""You are flagging likely German tax-deductible items from David's recent spending.

# Recent transactions
{_recent_transactions_text(3)}

Task (Markdown):
1. Likely deductibles grouped by type (Werbungskosten, Sonderausgaben, etc.)
2. For each: why it may qualify and what documentation to keep
3. Items to ASK the Steuerberater about
4. Rough deductible total (clearly marked as an estimate)
Do not overstate — mark uncertainty. Cite the deduction category.
"""
    return run_claude(prompt, timeout=600)


def bill_forecaster() -> str:
    """Predict next month's likely fixed outflows from recurring patterns."""
    prompt = f"""Predict David's likely FIXED outflows for next month from recurring patterns.

# Recent transactions
{_recent_transactions_text(3)}

Task (Markdown):
1. Detected recurring bills (merchant, typical €, day-of-month)
2. Next month's expected fixed-outflow total
3. Irregular-but-likely items to expect
4. Confidence note per line
"""
    return run_claude(prompt, timeout=600)
