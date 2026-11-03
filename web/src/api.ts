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
  // Windows only
  speech_provider?: "piper" | "microsoft"
  message_endpoint_id?: string
  preview_endpoint_id?: string
  hotkey?: string
}
export type MicrosoftVoice = { id: string; label: string; name: string; language: string; gender: Voice["gender"] }
export type State = {
  platform: "linux" | "windows"
  config: Config
  voices: Voice[]
  outputs: { name: string; description: string }[]
  microsoft: { voices: MicrosoftVoice[]; status: string }
  discordInput: string
  errors: string[] // parts of the state Python could not read
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
  open_voices_folder: () => Promise<void>
  fit_overlay: (height: number) => Promise<void>
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
  const refresh = useCallback(
    () =>
      api.state().then(
        (s) => {
          setState(s)
          if (s.errors?.length) setError(s.errors.join(" · "))
        },
        // Without state the pages render nothing, so surface why instead of a blank window.
        (e: unknown) => setError(`Could not load settings: ${e instanceof Error ? e.message : String(e)}`)
      ),
    [api]
  )

  useEffect(() => {
    window.casprRefresh = refresh
    window.casprError = setError
    refresh()
    // Re-read voices/outputs when the window comes back, e.g. after plugging in headphones.
    window.addEventListener("focus", refresh)
    return () => window.removeEventListener("focus", refresh)
  }, [refresh])

  const set = <K extends keyof Config>(name: K, value: Config[K]) => {
    // Optimistic so knobs and switches track the pointer without a round trip.
    setState((s) => s && { ...s, config: { ...s.config, [name]: value } })
    // A rejected setting (e.g. an invalid hotkey) shows its error and restores the saved value.
    api.set(name, value).catch((e: unknown) => {
      setError(e instanceof Error ? e.message : String(e))
      refresh()
    })
  }
  return { state, set, error, setError }
}

/** "en-GB" → 🇬🇧 (regional-indicator pair); "" when there is no country part. */
export function flagForLanguage(language: string) {
  const country = language.split("-")[1]?.toUpperCase() ?? ""
  return /^[A-Z]{2}$/.test(country) ? String.fromCodePoint(...[...country].map((c) => 0x1f1a5 + c.charCodeAt(0))) : ""
}

// "🇬🇧 Alan" → ["🇬🇧", "Alan"]
export function splitFlag(name: string): [string, string] {
  const [first, ...rest] = name.split(" ")
  return /\p{Regional_Indicator}/u.test(first) ? [first, rest.join(" ")] : ["🔊", name]
}
