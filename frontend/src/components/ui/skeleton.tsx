import type { HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

type SkeletonProps = HTMLAttributes<HTMLDivElement>

/**
 * Loading placeholder with a subtle shimmer, built from the same panel tokens
 * as everything else — so it reads as "loading" in both themes instead of a
 * flat dark rectangle. Use to reserve layout while server data loads.
 */
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "rounded border border-border bg-bg-panel",
        "bg-[linear-gradient(90deg,rgb(var(--color-bg-panel))_0%,rgb(var(--color-bg-panel-hover))_50%,rgb(var(--color-bg-panel))_100%)] bg-[length:200%_100%]",
        "animate-shimmer",
        className,
      )}
      {...props}
    />
  )
}
