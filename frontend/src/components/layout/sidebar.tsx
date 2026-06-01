import { NavLink } from "react-router-dom"
import { cn } from "@/lib/utils"

interface NavLinkDef {
  to: string
  label: string
}

interface NavGroup {
  label: string
  links: NavLinkDef[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "main",
    links: [
      { to: "/", label: "home" },
      { to: "/tasks", label: "tasks" },
      { to: "/projects", label: "projects" },
      { to: "/ideas", label: "ideas" },
      { to: "/inbox", label: "inbox" },
    ],
  },
  {
    label: "finance",
    links: [
      { to: "/portfolio", label: "portfolio" },
      { to: "/money", label: "money" },
      { to: "/watchlist", label: "watchlist" },
    ],
  },
  {
    label: "life",
    links: [
      { to: "/career", label: "career" },
      { to: "/brand", label: "brand" },
      { to: "/reading", label: "reading" },
    ],
  },
  {
    label: "system",
    links: [
      { to: "/background-runs", label: "background runs" },
      { to: "/settings", label: "settings" },
      { to: "/calendar", label: "calendar" },
    ],
  },
]

/**
 * Fixed 220px nav sidebar. Lowercase links grouped under small-caps headers.
 * Active link: accent text with a thin accent left border.
 */
export function Sidebar() {
  return (
    <nav className="w-[220px] shrink-0 border-r border-border bg-bg-panel overflow-y-auto py-4">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="mb-6 px-3">
          <div className="label px-2 mb-1.5">{group.label}</div>
          <ul className="space-y-0.5">
            {group.links.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "block rounded-sm border-l-2 px-2 py-1.5 text-sm transition-colors",
                      isActive
                        ? "border-accent text-accent bg-bg-panel-hover"
                        : "border-transparent text-text-secondary hover:text-text hover:bg-bg-panel-hover",
                    )
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}
