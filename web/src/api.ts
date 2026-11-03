import { useCallback, useEffect, useState } from "react"

export type Voice = { id: string; name: string; detail: string }
export type Config = {
  model_path: string
  microsoft_voice_id: string
  local_monitor: boolean
  local_output: string
  speech_volume: number
  playback_delay_seconds: number
  debug_notifications: boolean
}
export type State = {
  config: Config
  voices: Voice[]
  outputs: { name: string; description: string }[]
  microsoft: { voices: { id: string; label: string }[]; status: string }
  discordInput: string
}
export type Api = {
  kind: () => Promise<"overlay" | "settings">
  state: () => Promise<State>
  set: <K extends keyof Config>(name: K, value: Config[K]) => Promise<void>
  speak: (text: string) => Promise<void>
  sample: () => Promise<void>
  open_overlay: () => Promise<void>
  close: () => Promise<void>
  quit: () => Promise<void>
}

declare global {
  interface Window {
    pywebview?: { api: Api }
    casprError?: (message: string) => void
    casprRefresh?: () => void
  }
}

export function whenApiReady(): Promise<Api> {
  if (window.pywebview?.api) return Promise.resolve(window.pywebview.api)
  return new Promise((resolve) =>
    window.addEventListener("pywebviewready", () => resolve(window.pywebview!.api), { once: true })
  )
}

/** Python-owned state, refetched whenever any window changes a setting. */
export function useCasprState(api: Api) {
  const [state, setState] = useState<State>()
  const [error, setError] = useState("")
  const refresh = useCallback(() => api.state().then(setState), [api])

  useEffect(() => {
    window.casprRefresh = refresh
    window.casprError = setError
    refresh()
  }, [refresh])

  const set = <K extends keyof Config>(name: K, value: Config[K]) => {
    // Optimistic so knobs and switches track the pointer without a round trip.
    setState((s) => s && { ...s, config: { ...s.config, [name]: value } })
    api.set(name, value)
  }
  return { state, set, error, setError }
}

// "🇬🇧 Alan" → ["🇬🇧", "Alan"]
export function splitFlag(name: string): [string, string] {
  const [first, ...rest] = name.split(" ")
  return /\p{Regional_Indicator}/u.test(first) ? [first, rest.join(" ")] : ["🔊", name]
}
