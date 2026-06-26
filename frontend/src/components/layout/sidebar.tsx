import { NavLink } from "react-router-dom"
import {
  Wallet,
  FolderKanban,
  Activity,
  Search,
  Cog,
  type LucideIcon,
} from "lucide-react"
import { openSearch } from "@/lib/search-bus"
import { cn } from "@/lib/utils"

interface NavLinkDef {
  label: string
  icon: LucideIcon
  to?: string // route link…
  action?: () => void // …or an action (e.g. open the search palette)
}

interface NavGroup {
  label: string
  links: NavLinkDef[]
}

// v3 sidebar (Dashboard_v3_Build_Spec § f): exactly the two pillars +
// Background Runs + Search + Settings. Everything else is folded into a pillar
// and stays reachable by URL only (no sidebar entry).
const NAV_GROUPS: NavGroup[] = [
  {
    label: "pillars",
    links: [
      { to: "/portfolio", label: "portfolio", icon: Wallet },
      { to: "/projects", label: "projects", icon: FolderKanban },
    ],
  },
  {
    label: "system",
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
  return (
    <>
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="mb-6 px-3">
          <div className={cn("label px-2 mb-1.5", !showLabels && "hidden min-[1100px]:block")}>
            {group.label}
          </div>
          <ul className="space-y-0.5">
            {group.links.map((link) => {
              const Icon = link.icon
              const labelSpan = (
                <span className={cn("truncate capitalize", !showLabels && "hidden min-[1100px]:inline")}>
                  {link.label}
                </span>
              )
              return (
                <li key={link.label}>
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
              )
            })}
          </ul>
        </div>
      ))}
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
