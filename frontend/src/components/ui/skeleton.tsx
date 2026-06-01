import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

type SkeletonProps = HTMLAttributes<HTMLDivElement>

/**
 * Loading placeholder with a subtle `bg-panel` shimmer. Use to reserve layout
 * while server data loads.
 */
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "rounded bg-bg-panel",
        "bg-[linear-gradient(90deg,#11161D_0%,#161C25_50%,#11161D_100%)] bg-[length:200%_100%]",
        "animate-shimmer",
        className,
      )}
      {...props}
    />
  )
}
