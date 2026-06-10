import { NavLink } from "react-router-dom"
import {
  Home,
  CalendarRange,
  Rocket,
  Wallet,
  GraduationCap,
  Video,
  Cog,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface NavLinkDef {
  to: string
  label: string
  icon: LucideIcon
}

interface NavGroup {
  label: string
  links: NavLinkDef[]
}

// v2 sidebar — exactly the 7 locked pages (Dashboard_v2_Spec.md §3).
// Dropped/merged out of the nav: Inbox (Quick Capture button lives on every
// page instead) and Reading (folded into the Home Brain/System focus card).
const NAV_GROUPS: NavGroup[] = [
  {
    label: "main",
    links: [
      { to: "/", label: "home", icon: Home },
      // v2: Plan absorbs planner + tasks + calendar + daily priorities.
      { to: "/plan", label: "plan", icon: CalendarRange },
      // v2: Ventures absorbs projects + ideas (company of agents).
      { to: "/ventures", label: "ventures", icon: Rocket },
    ],
  },
  {
    label: "finance",
    links: [
      // v2: Wealth absorbs portfolio + money + watchlist + decision journal.
      { to: "/wealth", label: "wealth", icon: Wallet },
    ],
  },
  {
    label: "life",
    links: [
      { to: "/career", label: "career", icon: GraduationCap },
      { to: "/brand", label: "brand", icon: Video },
    ],
  },
  {
    label: "system",
    links: [
      // v2: Background Runs + Settings + diagnostics + Skills & Agents Registry
      // merged into one System page.
      { to: "/system", label: "system", icon: Cog },
    ],
  },
]

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
              return (
                <li key={link.to}>
                  <NavLink
                    to={link.to}
                    end={link.to === "/"}
                    onClick={onNavigate}
                    aria-label={link.label}
                    title={link.label}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 rounded-sm border-l-2 px-2 py-1.5 text-sm transition-colors",
                        isActive
                          ? "border-accent text-accent bg-bg-panel-hover"
                          : "border-transparent text-text-secondary hover:border-accent-dim hover:text-text hover:bg-bg-panel-hover",
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className={cn("truncate capitalize", !showLabels && "hidden min-[1100px]:inline")}>
                      {link.label}
                    </span>
                  </NavLink>
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
