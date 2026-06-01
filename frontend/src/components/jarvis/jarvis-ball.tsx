import { useMemo, useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"
import { cn } from "@/lib/utils"

export type JarvisState = "idle" | "listening" | "processing" | "speaking"

interface JarvisBallProps {
  size?: "large" | "small"
  state?: JarvisState
  onClick?: () => void
  className?: string
}

/** Navy palette — every state is a variation of navy, brighter when active. */
const STATE_COLOR: Record<JarvisState, string> = {
  idle: "#1E3A8A", // blue-800 — resting
  processing: "#1D4ED8", // blue-700 — thinking
  listening: "#3B82F6", // blue-500 — responding
  speaking: "#60A5FA", // blue-400 — speaking back
}

/**
 * 3D particle orb (the "Jarvis ball"). Two sizes: `large` is the Home
 * centerpiece, `small` sits in the header on other pages. Click to open the
 * briefing overlay.
 */
export function JarvisBall({
  size = "large",
  state = "idle",
  onClick,
  className,
}: JarvisBallProps) {
  const dimClass = size === "large" ? "w-[450px] h-[450px]" : "w-[60px] h-[60px]"
  // Fewer particles on the small ball and on phones (perf — see spec notes).
  const isSmallScreen = typeof window !== "undefined" && window.innerWidth < 640
  const count = size === "small" ? 400 : isSmallScreen ? 400 : 800

  return (
    <div
      className={cn(
        dimClass,
        "cursor-pointer transition-transform duration-300 hover:scale-105",
        className,
      )}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      aria-label={onClick ? "open jarvis briefing" : undefined}
    >
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={0.6} />
        <ParticleSphere state={state} count={count} />
      </Canvas>
    </div>
  )
}

function ParticleSphere({ state, count }: { state: JarvisState; count: number }) {
  const groupRef = useRef<THREE.Group>(null!)

  // Base positions on a unit sphere via Fibonacci distribution. Kept immutable;
  // per-frame oscillation is written into a separate displacement buffer so the
  // base layout never drifts.
  const base = useMemo(() => {
    const arr = new Float32Array(count * 3)
    const goldenRatio = (1 + Math.sqrt(5)) / 2
    for (let i = 0; i < count; i++) {
      const theta = (2 * Math.PI * i) / goldenRatio
      const phi = Math.acos(1 - (2 * (i + 0.5)) / count)
      arr[i * 3] = Math.sin(phi) * Math.cos(theta)
      arr[i * 3 + 1] = Math.sin(phi) * Math.sin(theta)
      arr[i * 3 + 2] = Math.cos(phi)
    }
    return arr
  }, [count])

  // The geometry whose position attribute we mutate each frame.
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    geo.setAttribute("position", new THREE.BufferAttribute(base.slice(), 3))
    return geo
  }, [base])

  useFrame((frameState, delta) => {
    const group = groupRef.current
    if (!group) return
    const t = frameState.clock.getElapsedTime()

    // Continuous slow rotation.
    group.rotation.y += delta * 0.1
    group.rotation.x += delta * 0.05

    // Breathing scale — speed/amplitude vary by state.
    const breath =
      state === "listening"
        ? 1 + Math.sin(t * 4) * 0.15
        : state === "speaking"
          ? 1 + Math.sin(t * 8) * 0.08
          : state === "processing"
            ? 1 + Math.sin(t * 6) * 0.05
            : 1 + Math.sin(t * 1.5) * 0.04 // idle
    group.scale.setScalar(breath)

    // Subtle per-particle radial oscillation, written into the live buffer.
    const attr = geometry.attributes.position as THREE.BufferAttribute
    const out = attr.array as Float32Array
    for (let i = 0; i < count; i++) {
      const x = base[i * 3]
      const y = base[i * 3 + 1]
      const z = base[i * 3 + 2]
      const factor = 1 + Math.sin(t * 2 + i * 0.1) * 0.03
      out[i * 3] = x * factor
      out[i * 3 + 1] = y * factor
      out[i * 3 + 2] = z * factor
    }
    attr.needsUpdate = true
  })

  const color = STATE_COLOR[state]

  return (
    <group ref={groupRef}>
      <points geometry={geometry}>
        <pointsMaterial
          color={color}
          size={0.05}
          sizeAttenuation
          transparent
          opacity={0.9}
        />
      </points>
      {/* Inner glow sphere. */}
      <mesh scale={0.6}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.06} />
      </mesh>
    </group>
  )
}
