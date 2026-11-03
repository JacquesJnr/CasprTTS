import { useCallback, useEffect, useState } from "react"

export type Voice = { id: string; name: string; detail: string; gender: "male" | "female" | "" }
export type QuickOption = { name: string; phrases: string[] }
export const MAX_QUICK_OPTIONS = 5
export type Config = {
  model_path: string
  microsoft_voice_id: string
  local_monitor: boolean
  local_output: string
  speech_volume: number
  playback_delay_seconds: number
  debug_notifications: boolean
  quick_options: QuickOption[]
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
  speak_quick: (index: number) => Promise<void>
  history_previous: (current: string) => Promise<string>
  history_next: () => Promise<string>
  sample: () => Promise<void>
  open_overlay: () => Promise<void>
  open_settings: (section?: string) => Promise<void>
  take_focus_section: () => Promise<string>
  close: () => Promise<void>
  quit: () => Promise<void>
}

declare global {
  interface Window {
    pywebview?: { api: Api }
    casprError?: (message: string) => void
    casprRefresh?: () => void
    casprFocus?: (section: string) => void
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
