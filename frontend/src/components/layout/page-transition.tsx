import { motion } from "framer-motion"
import type { ReactNode } from "react"

/**
 * Fade-in + slight slide-up on mount (200ms). Key this by route path so it
 * re-runs on navigation. Respects reduced-motion automatically via Framer.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  )
}
