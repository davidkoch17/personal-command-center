import { useMemo, useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"
import { cn } from "@/lib/utils"

export type JarvisState = "idle" | "thinking" | "speaking" | "listening" | "routing"

interface JarvisBallProps {
  size?: "large" | "small"
  state?: JarvisState
  onClick?: () => void
  className?: string
}

/** Navy palette — every state is a variation of navy, brighter when active. */
const STATE_COLOR: Record<JarvisState, string> = {
  idle: "#1E3A8A", // blue-800 — resting, deep navy
  thinking: "#1D4ED8", // blue-700 — assembling
  routing: "#1D4ED8", // blue-700 — same as thinking
  listening: "#3B82F6", // blue-500 — attentive
  speaking: "#60A5FA", // blue-400 — brightest, speaking back
}

/**
 * 3D particle orb (the "Jarvis ball"). Two sizes: `large` is the Home
 * centerpiece, `small` sits in the header on other pages. Click to start the
 * spoken briefing flow.
 *
 * The orb is the entire interaction surface — its visual state telegraphs what
 * Jarvis is doing: a gentle breathing idle, a quick thinking pulse, expansive
 * outward ripples while speaking, and an attentive, contracted sonar-pinging
 * pose while listening.
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
      aria-label={onClick ? "talk to jarvis" : undefined}
    >
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={0.6} />
        <ParticleSphere state={state} count={count} />
      </Canvas>
    </div>
  )
}

/**
 * A single expanding "sonar" ring used only while listening: it grows from
 * scale 0.85 → 1.5 over 1.2s while fading out, then repeats — reading clearly
 * as outward pings, distinct from the speaking ripples.
 */
function SonarRing({ active }: { active: boolean }) {
  const ringRef = useRef<THREE.Mesh>(null!)
  useFrame((state) => {
    if (!ringRef.current || !active) {
      if (ringRef.current) ringRef.current.scale.setScalar(0)
      return
    }
    const t = state.clock.getElapsedTime()
    const cycle = (t % 1.2) / 1.2 // 0 → 1 over 1.2s
    ringRef.current.scale.setScalar(0.85 + cycle * 0.65)
    ;(ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.4 * (1 - cycle)
  })
  return (
    <mesh ref={ringRef}>
      <ringGeometry args={[1, 1.03, 64]} />
      <meshBasicMaterial color="#3B82F6" transparent opacity={0.4} side={THREE.DoubleSide} />
    </mesh>
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

    // Rotation speed by state: brisk while thinking/routing, near-still while
    // listening (attentive), gentle otherwise.
    const rotSpeed =
      state === "thinking" || state === "routing"
        ? 0.3
        : state === "listening"
          ? 0.05
          : 0.1 // idle, speaking
    group.rotation.y += delta * rotSpeed
    group.rotation.x += delta * rotSpeed * 0.5

    // Overall scale / breathing — speed, amplitude and baseline vary by state.
    let breath: number
    if (state === "speaking") {
      breath = 1 + Math.sin(t * 4) * 0.06
    } else if (state === "thinking" || state === "routing") {
      breath = 1 + Math.sin(t * 6) * 0.05 // quick pulse
    } else if (state === "listening") {
      breath = 0.85 + Math.sin(t * 2) * 0.02 // contracted inward, attentive
    } else {
      breath = 1 + Math.sin(t * 1.5) * 0.04 // idle — gentle breathing
    }
    group.scale.setScalar(breath)

    // Per-particle radial oscillation, written into the live buffer. Speaking
    // gets expansive outward ripples; other states a subtle shimmer.
    const speaking = state === "speaking"
    const amp = speaking ? 0.15 : 0.03
    const freq = speaking ? 4 : 2
    const attr = geometry.attributes.position as THREE.BufferAttribute
    const out = attr.array as Float32Array
    for (let i = 0; i < count; i++) {
      const x = base[i * 3]
      const y = base[i * 3 + 1]
      const z = base[i * 3 + 2]
      const factor = 1 + Math.sin(t * freq + i * 0.1) * amp
      out[i * 3] = x * factor
      out[i * 3 + 1] = y * factor
      out[i * 3 + 2] = z * factor
    }
    attr.needsUpdate = true
  })

  const color = STATE_COLOR[state]
  // Larger, looser particles when speaking; smaller, focused when listening.
  const particleSize = state === "speaking" ? 0.07 : state === "listening" ? 0.04 : 0.05
  // Inner glow brightens while thinking/routing/speaking.
  const innerGlow =
    state === "speaking"
      ? 0.12
      : state === "thinking" || state === "routing"
        ? 0.1
        : 0.06

  return (
    <group ref={groupRef}>
      <points geometry={geometry}>
        <pointsMaterial
          color={color}
          size={particleSize}
          sizeAttenuation
          transparent
          opacity={0.9}
        />
      </points>

      {/* Inner glow sphere. */}
      <mesh scale={0.6}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial color={color} transparent opacity={innerGlow} />
      </mesh>

      {/* Outer glow ring — only while speaking (back-side sphere = soft halo). */}
      {state === "speaking" && (
        <mesh scale={1.3}>
          <sphereGeometry args={[1, 32, 32]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.08}
            side={THREE.BackSide}
          />
        </mesh>
      )}

      {/* Expanding sonar ping — only while listening. */}
      <SonarRing active={state === "listening"} />
    </group>
  )
}
