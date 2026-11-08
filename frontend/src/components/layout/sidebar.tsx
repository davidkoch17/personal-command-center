import { Fragment, useState } from "react"
import { NavLink } from "react-router-dom"
import {
  TrendingUp,
  Wallet,
  PiggyBank,
  FolderKanban,
  ListTodo,
  Sun,
  Activity,
  Search,
  Cog,
  ChevronDown,
  type LucideIcon,
} from "lucide-react"
import { openSearch } from "@/lib/search-bus"
import { cn } from "@/lib/utils"

interface NavLinkDef {
  label: string
  icon: LucideIcon
  to?: string // route link…
  action?: () => void // …or an action (e.g. open the search palette)
  dividerAfter?: boolean // renders a visual divider below this entry
}

interface NavGroup {
  label: string
  links: NavLinkDef[]
  collapsible?: boolean // header becomes a chevron toggle; state persisted
}

const COLLAPSE_KEY = "cc-nav-collapsed"

function readCollapsed(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_KEY) ?? "") ?? {}
  } catch {
    return { system: true } // system starts collapsed for a cleaner rail
  }
}

function writeCollapsed(value: Record<string, boolean>): void {
  try {
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify(value))
  } catch {
    /* storage disabled — state just won't persist */
  }
}

// v4 sidebar: Net Worth + 3 pillars (added Oct 2026 per David's explicit
// override of the v3 lock). v3 (Dashboard_v3_Build_Spec § f) originally
// locked exactly two pillars; Cash Flow was added as a deliberate third
// (income/expense ledger, separate domain from Portfolio's net worth/
// holdings), and Net Worth is the fourth — a holistic bank+brokerage+holdings
// rollup, separate again from both. Everything else is folded into a pillar
// and stays reachable by URL only (no sidebar entry).
//
// Nov 2026: pillars split into "finance" (money views) and "planning"
// (projects + to-dos) so the two kinds of work read as separate areas; the
// "system" group collapses behind a chevron to keep the rail calm.
const NAV_GROUPS: NavGroup[] = [
  {
    label: "overview",
    links: [{ to: "/today", label: "today", icon: Sun }],
  },
  {
    label: "finance",
    links: [
      { to: "/networth", label: "net worth", icon: TrendingUp, dividerAfter: true },
      { to: "/portfolio", label: "portfolio", icon: Wallet },
      { to: "/cashflow", label: "cash flow", icon: PiggyBank },
    ],
  },
  {
    label: "planning",
    links: [
      { to: "/projects", label: "projects", icon: FolderKanban },
      { to: "/todos", label: "to-dos", icon: ListTodo },
    ],
  },
  {
    label: "system",
    collapsible: true,
    links: [
      { to: "/background-runs", label: "background runs", icon: Activity },
      { label: "search", icon: Search, action: openSearch },
      { to: "/settings", label: "settings", icon: Cog },
    ],
  },
]

const ITEM_CLASS =
  "flex w-full items-center gap-2.5 rounded-sm border-l-2 px-2 py-1.5 text-sm transition-colors"
const INACTIVE_CLASS =
  "border-transparent text-text-secondary hover:border-accent-dim hover:text-text hover:bg-bg-panel-hover"
const ACTIVE_CLASS = "border-accent text-accent bg-bg-panel-hover"

function NavList({
  showLabels,
  onNavigate,
}: {
  showLabels: boolean
  onNavigate?: () => void
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(readCollapsed)

  function toggle(label: string) {
    setCollapsed((c) => {
      const next = { ...c, [label]: !c[label] }
      writeCollapsed(next)
      return next
    })
  }

  return (
    <>
      {NAV_GROUPS.map((group, gi) => {
        const isCollapsed = !!(group.collapsible && collapsed[group.label])
        return (
        <div
          key={group.label}
          className={cn("px-3", gi > 0 && "mt-4 border-t border-border pt-4")}
        >
          {group.collapsible ? (
            <button
              type="button"
              onClick={() => toggle(group.label)}
              aria-expanded={!isCollapsed}
              title={isCollapsed ? `show ${group.label}` : `hide ${group.label}`}
              className="label mb-1.5 flex w-full items-center justify-center gap-1 rounded-sm px-2 py-0.5 hover:text-text-secondary min-[1100px]:justify-between"
            >
              <span className={cn(!showLabels && "hidden min-[1100px]:inline")}>{group.label}</span>
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", isCollapsed && "-rotate-90")}
              />
            </button>
          ) : (
            <div className={cn("label px-2 mb-1.5", !showLabels && "hidden min-[1100px]:block")}>
              {group.label}
            </div>
          )}
          {!isCollapsed && (
          <ul className="space-y-0.5">
            {group.links.map((link) => {
              const Icon = link.icon
              const labelSpan = (
                <span className={cn("truncate capitalize", !showLabels && "hidden min-[1100px]:inline")}>
                  {link.label}
                </span>
              )
              return (
                <Fragment key={link.label}>
                  <li>
                    {link.to ? (
                      <NavLink
                        to={link.to}
                        onClick={onNavigate}
                        aria-label={link.label}
                        title={link.label}
                        className={({ isActive }) =>
                          cn(ITEM_CLASS, isActive ? ACTIVE_CLASS : INACTIVE_CLASS)
                        }
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        {labelSpan}
                      </NavLink>
                    ) : (
                      <button
                        type="button"
                        aria-label={link.label}
                        title={`${link.label} (⌘K)`}
                        onClick={() => {
                          link.action?.()
                          onNavigate?.()
                        }}
                        className={cn(ITEM_CLASS, INACTIVE_CLASS)}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        {labelSpan}
                      </button>
                    )}
                  </li>
                  {/* Same visual pattern as the gap between groups (a border +
                      vertical space), used here to set Net Worth apart within
                      the finance group without a separate label. */}
                  {link.dividerAfter && (
                    <li aria-hidden="true" className="my-2 border-t border-border" />
                  )}
                </Fragment>
              )
            })}
          </ul>
          )}
        </div>
        )
      })}
    </>
  )
}

/**
 * Desktop nav rail. Full (220px, labelled) at ≥1100px, icon-only (64px) from
 * 800–1100px, hidden below 800px (use the mobile drawer there).
 */
export function Sidebar() {
  return (
    <nav className="no-print hidden min-[800px]:block w-16 min-[1100px]:w-[220px] shrink-0 overflow-y-auto border-r border-border bg-bg-panel py-4 transition-[width]">
      <NavList showLabels={false} />
    </nav>
  )
}

/** Mobile slide-over drawer (<800px), toggled by the header hamburger. */
export function MobileNav({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  if (!open) return null
  return (
    <div className="no-print fixed inset-0 z-[80] min-[800px]:hidden">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <nav className="absolute left-0 top-0 h-full w-64 overflow-y-auto border-r border-border bg-bg-panel py-4">
        <NavList showLabels onNavigate={onClose} />
      </nav>
    </div>
  )
}
