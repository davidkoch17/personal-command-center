import { NavLink } from "react-router-dom"
import {
  Home,
  CalendarRange,
  ListChecks,
  FolderKanban,
  Lightbulb,
  Inbox,
  LineChart,
  Wallet,
  Eye,
  NotebookPen,
  GraduationCap,
  Video,
  BookOpen,
  Activity,
  Settings,
  Calendar,
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

const NAV_GROUPS: NavGroup[] = [
  {
    label: "main",
    links: [
      { to: "/", label: "home", icon: Home },
      { to: "/planner", label: "planner", icon: CalendarRange },
      { to: "/tasks", label: "tasks", icon: ListChecks },
      { to: "/projects", label: "projects", icon: FolderKanban },
      { to: "/ideas", label: "ideas", icon: Lightbulb },
      { to: "/inbox", label: "inbox", icon: Inbox },
    ],
  },
  {
    label: "finance",
    links: [
      { to: "/portfolio", label: "portfolio", icon: LineChart },
      { to: "/money", label: "money", icon: Wallet },
      { to: "/watchlist", label: "watchlist", icon: Eye },
      { to: "/decision-journal", label: "journal", icon: NotebookPen },
    ],
  },
  {
    label: "life",
    links: [
      { to: "/career", label: "career", icon: GraduationCap },
      { to: "/brand", label: "brand", icon: Video },
      { to: "/reading", label: "reading", icon: BookOpen },
    ],
  },
  {
    label: "system",
    links: [
      { to: "/background-runs", label: "background runs", icon: Activity },
      { to: "/settings", label: "settings", icon: Settings },
      { to: "/calendar", label: "calendar", icon: Calendar },
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
                    <span className={cn("truncate", !showLabels && "hidden min-[1100px]:inline")}>
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
