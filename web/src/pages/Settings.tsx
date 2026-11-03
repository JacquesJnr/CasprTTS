import { useEffect, useState, type CSSProperties, type ReactNode } from "react"
import { motion } from "motion/react"
import { Mic, Play, Plus, Trash2 } from "lucide-react"

import { KnobSlider } from "@/components/watermelon/knob-slider"
import { GenderGlyph } from "@/components/gender-glyph"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { commandSlug } from "@/commands"
import { flagForLanguage, MAX_QUICK_OPTIONS, splitFlag, useCasprState, type Api, type QuickOption, type Voice } from "@/api"

// Radix Select reserves "" for "no value", so the default output gets a sentinel.
const DEFAULT_OUTPUT = "__default__"

function Module({ id, highlighted, index, title, action, children }: {
  id?: string; highlighted?: boolean; index: string; title: string; action?: ReactNode; children: ReactNode
}) {
  return (
    <section
      id={id}
      className={`scroll-mt-4 rounded-xl border bg-card p-3 transition-[border-color,box-shadow] duration-700 ${
        highlighted ? "border-primary/60 shadow-glow" : "border-border shadow-lift"
      }`}
    >
      <header className="mb-3 flex min-h-8 items-center justify-between gap-2 px-1">
        <h2 className="text-[15px] font-[510]">
          <span className="mr-1.5 font-mono text-[12px] text-fog">{index}</span>{title}
        </h2>
        {action}
      </header>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  )
}

function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="px-1 text-[13px] text-steel">{label}</span>
      {children}
      {help && <span className="px-1 text-[12px] text-muted-foreground">{help}</span>}
    </div>
  )
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <code className="rounded-[4px] bg-gunmetal px-1.5 py-0.5 font-mono text-[12px] text-muted-foreground select-all">
      {children}
    </code>
  )
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-md border border-border bg-muted px-3 py-2.5 text-[13px]">
      {label}
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  )
}

const button = "rounded-md px-3.5 py-1.5 text-[13px] font-[510] transition outline-none focus-visible:shadow-glow disabled:opacity-50"
const primary = `${button} bg-primary text-primary-foreground shadow-glow hover:brightness-110`
const subtle = `${button} border border-input bg-secondary text-steel hover:bg-accent`

const field = "rounded-md border border-input bg-muted px-3 py-2 text-[13px] outline-none transition placeholder:text-fog focus:border-primary/70 focus:shadow-glow"
const iconButton = "flex size-8 shrink-0 items-center justify-center rounded-md border border-input bg-secondary text-steel outline-none transition hover:bg-accent focus-visible:shadow-glow disabled:opacity-40"

function VoiceCard({ flag, name, detail, gender, active, onSelect }: {
  flag: string; name: string; detail: string; gender: Voice["gender"]; active: boolean; onSelect: () => void
}) {
  return (
    <button
      role="radio"
      aria-checked={active}
      onClick={onSelect}
      className="relative flex items-center gap-3 rounded-md border border-border bg-muted px-3 py-2.5 text-left outline-none hover:bg-accent/40 focus-visible:shadow-glow"
    >
      {active && (
        <motion.span
          layoutId="voice-active"
          transition={{ type: "spring", stiffness: 500, damping: 35 }}
          className="absolute -inset-px rounded-md border border-primary/70 bg-primary/[0.04] shadow-glow"
        />
      )}
      <span className="relative flex items-center gap-1">
        <span className="text-xl" aria-hidden>{flag || "🔊"}</span>
        <GenderGlyph gender={gender} />
      </span>
      <span className="relative flex flex-col">
        <span className="text-[13px] font-[510]">{name}</span>
        <span className="text-[12px] text-muted-foreground">{detail}</span>
      </span>
    </button>
  )
}

const regionName = (language: string) => {
  const region = language.split("-")[1]
  try {
    return region ? new Intl.DisplayNames(["en"], { type: "region" }).of(region.toUpperCase()) ?? language : language
  } catch {
    return language
  }
}

function HotkeyField({ value, onCommit }: { value: string; onCommit: (value: string) => void }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <input
      aria-label="Overlay shortcut"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => draft.trim() !== value && onCommit(draft.trim())}
      onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      className="w-40 rounded-[4px] border border-input bg-muted px-2 py-1 text-right font-mono text-[12px] outline-none focus:border-primary/70 focus:shadow-glow"
    />
  )
}

// Drafts commit on blur so typing (e.g. a new line) isn't normalized away mid-edit.
function QuickOptionEditor({ option, onChange, onRemove, onSay }: {
  option: QuickOption
  onChange: (option: QuickOption) => void
  onRemove: () => void
  onSay: () => void
}) {
  const savedPhrases = option.phrases.join("\n")
  const [name, setName] = useState(option.name)
  const [phrases, setPhrases] = useState(savedPhrases)
  // Re-sync when the saved value changes (own commit, deletion shifting rows, other window).
  useEffect(() => setName(option.name), [option.name])
  useEffect(() => setPhrases(savedPhrases), [savedPhrases])
  const commit = () => onChange({ name: name.trim(), phrases: phrases.split("\n").map((p) => p.trim()).filter(Boolean) })

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-2 rounded-md border border-border bg-muted p-2.5"
    >
      <div className="flex items-center gap-2">
        <input
          autoFocus={!option.name}
          aria-label="Category name"
          placeholder="Category name, e.g. Greeting"
          maxLength={24}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          className={`${field} min-w-0 flex-1 font-[510]`}
        />
        <button className={iconButton} title="Say a random phrase now" disabled={!option.phrases.length} onClick={onSay}>
          <Play size={14} />
        </button>
        <button className={`${iconButton} hover:text-destructive`} title="Delete category" onClick={onRemove}>
          <Trash2 size={14} />
        </button>
      </div>
      <textarea
        aria-label={`${name || "Category"} phrases, one per line`}
        placeholder={"One phrase per line\nHello\nHey there"}
        rows={Math.min(6, Math.max(3, phrases.split("\n").length))}
        value={phrases}
        onChange={(e) => setPhrases(e.target.value)}
        onBlur={commit}
        className={`${field} resize-none leading-relaxed`}
      />
      <span className="px-1 font-mono text-[11px] text-fog">
        {option.phrases.length} phrase{option.phrases.length === 1 ? "" : "s"} · one picked at random
        {option.name && <> · type <span className="text-primary">/{commandSlug(option.name)}</span> in a message</>}
      </span>
    </motion.div>
  )
}

export function Settings({ api }: { api: Api }) {
  const { state, set, error } = useCasprState(api)
  const [sampling, setSampling] = useState(false)
  const [highlight, setHighlight] = useState("")

  // Jump to a section on request (e.g. the overlay's "+" chip) and briefly glow it.
  useEffect(() => {
    if (!state) return
    window.casprFocus = (section) => {
      document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" })
      setHighlight(section)
      setTimeout(() => setHighlight(""), 1400)
    }
    api.take_focus_section().then((section) => section && window.casprFocus?.(section))
  }, [api, !state]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) return null
  const { config } = state
  const windows = state.platform === "windows"
  const provider = config.speech_provider ?? "piper"
  const useMicrosoft = windows && provider === "microsoft"
  // Windows samples play only on a separate preview output, never the device Stereo Mix records.
  const canSample = windows
    ? Boolean(config.preview_endpoint_id && config.preview_endpoint_id !== config.message_endpoint_id)
    : state.voices.length > 0
  const endpointIds = new Set(state.outputs.map((o) => o.name))
  const endpointValue = (id?: string) => (id && endpointIds.has(id) ? id : undefined)
  const outputValue = !config.local_output
    ? DEFAULT_OUTPUT
    : state.outputs.some((o) => o.name === config.local_output) ? config.local_output : undefined

  const sample = async () => {
    setSampling(true)
    await api.sample().finally(() => setSampling(false))
  }

  return (
    <div className="flex h-svh flex-col">
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[640px] flex-col gap-3 p-4">
          <header className="flex items-center gap-3 px-1 pb-1">
            <div className="flex size-9 items-center justify-center rounded-md border border-border bg-card">
              <Mic size={18} />
            </div>
            <div className="flex-1">
              <h1 className="text-[20px] leading-none font-[590] tracking-[-0.02em]">Caspr</h1>
              <p className="mt-1 text-[12px] text-muted-foreground">Your words. A little more soul.</p>
            </div>
            <span className="flex items-center gap-1.5 rounded-[4px] bg-gunmetal px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
              <span className="size-1.5 rounded-full bg-primary shadow-glow-sm" />TTS · offline
            </span>
          </header>

          {error && (
            <p role="alert" className="rounded-md border border-destructive/40 bg-muted px-3 py-2 text-[12px] text-destructive">{error}</p>
          )}

          <Module index="01" title={windows ? "Voice" : "Piper voice"} action={
            <button
              className={subtle}
              disabled={!canSample || sampling}
              title={canSample ? "Hear “I love text-to-speech” through headphones only" : "Choose a separate headphone output in Audio first"}
              onClick={sample}
            >
              {sampling ? "Sampling…" : "Sample voice"}
            </button>
          }>
            {windows && (
              <div role="radiogroup" aria-label="Speech provider" className="grid grid-cols-2 gap-1 rounded-md border border-border bg-muted p-1">
                {(["microsoft", "piper"] as const).map((p) => (
                  <button
                    key={p}
                    role="radio"
                    aria-checked={provider === p}
                    onClick={() => set("speech_provider", p)}
                    className={`rounded-[4px] px-3 py-1.5 text-[13px] outline-none transition focus-visible:shadow-glow ${
                      provider === p ? "border border-primary/60 bg-secondary text-foreground shadow-glow-sm" : "border border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {p === "microsoft" ? "Microsoft voices" : "Piper voices"}
                  </button>
                ))}
              </div>
            )}

            {useMicrosoft ? (
              state.microsoft.voices.length ? (
                <div role="radiogroup" aria-label="Microsoft voice" className="grid grid-cols-2 gap-2">
                  {state.microsoft.voices.map((v) => (
                    <VoiceCard
                      key={v.id}
                      flag={flagForLanguage(v.language)}
                      name={v.name.replace(/^Microsoft\s+/, "")}
                      detail={regionName(v.language)}
                      gender={v.gender}
                      active={v.id === config.microsoft_voice_id}
                      onSelect={() => set("microsoft_voice_id", v.id)}
                    />
                  ))}
                </div>
              ) : (
                <p className="px-1 text-[12px] text-muted-foreground">{state.microsoft.status}</p>
              )
            ) : (
              <div role="radiogroup" aria-label="Piper voice" className="grid grid-cols-2 gap-2">
                {state.voices.map((v) => {
                  const [flag, name] = splitFlag(v.name)
                  return (
                    <VoiceCard
                      key={v.id}
                      flag={flag}
                      name={name}
                      detail={v.detail}
                      gender={v.gender}
                      active={v.id === config.model_path}
                      onSelect={() => set("model_path", v.id)}
                    />
                  )
                })}
              </div>
            )}

            {windows && !useMicrosoft && (
              <div className="flex items-center justify-between gap-3 px-1 text-[12px] text-muted-foreground">
                Add a Piper .onnx voice and its .onnx.json file to the voices folder.
                <button className={subtle} onClick={() => api.open_voices_folder()}>Open voices folder</button>
              </div>
            )}

            {!windows && <Field
              label="Microsoft voices"
              help={`${state.microsoft.status} Microsoft playback is not available yet; messages and samples use Piper.`}
            >
              <Select
                value={config.microsoft_voice_id || undefined}
                onValueChange={(id) => set("microsoft_voice_id", id)}
                disabled={!state.microsoft.voices.length}
              >
                <SelectTrigger className="w-full bg-muted"><SelectValue placeholder="No voice selected" /></SelectTrigger>
                <SelectContent>
                  {state.microsoft.voices.map((v) => <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>}
            {useMicrosoft && config.microsoft_voice_id && !state.microsoft.voices.some((v) => v.id === config.microsoft_voice_id) && (
              <p className="px-1 text-[12px] text-destructive">{state.microsoft.status}</p>
            )}
          </Module>

          <Module index="02" title="Audio" action={
            <span className="flex items-center gap-2 text-[12px] text-muted-foreground">Discord input <Badge>{state.discordInput}</Badge></span>
          }>
            <div className="flex items-center gap-4">
              <div className="flex flex-col items-center gap-1">
                <KnobSlider
                  label="Speech volume"
                  value={config.speech_volume}
                  onChange={(v) => set("speech_volume", v)}
                  size={150}
                />
                <span className="font-mono text-[11px] text-fog">VOLUME</span>
              </div>
              {windows ? (
              <div className="flex flex-1 flex-col gap-2">
                <p className="px-1 text-[12px] text-muted-foreground">Discord hears everything the message output plays · 0% mutes</p>
                <Field label="Message output">
                  <Select value={endpointValue(config.message_endpoint_id)} onValueChange={(id) => set("message_endpoint_id", id)}>
                    <SelectTrigger className="w-full bg-muted">
                      <SelectValue placeholder={config.message_endpoint_id ? "Saved output not connected" : "Output that Stereo Mix records"} />
                    </SelectTrigger>
                    <SelectContent>
                      {state.outputs.map((o) => <SelectItem key={o.name} value={o.name}>{o.description}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </Field>
                <ToggleRow label="Hear speech in headphones" checked={config.local_monitor} onChange={(v) => set("local_monitor", v)} />
                <Field label="Headphone output" help={
                  config.preview_endpoint_id && config.preview_endpoint_id === config.message_endpoint_id
                    ? "Choose a different device from the message output." : "Samples play here only."
                }>
                  <Select value={endpointValue(config.preview_endpoint_id)} onValueChange={(id) => set("preview_endpoint_id", id)}>
                    <SelectTrigger className="w-full bg-muted">
                      <SelectValue placeholder={config.preview_endpoint_id ? "Saved output not connected" : "A different device, e.g. headphones"} />
                    </SelectTrigger>
                    <SelectContent>
                      {state.outputs.map((o) => <SelectItem key={o.name} value={o.name}>{o.description}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              ) : (
              <div className="flex flex-1 flex-col gap-2">
                <p className="px-1 text-[12px] text-muted-foreground">Mic + headphones · 0% mutes · Applies to next playback</p>
                <ToggleRow label="Hear speech in headphones" checked={config.local_monitor} onChange={(v) => set("local_monitor", v)} />
                <Field label="Headphone output">
                  <Select
                    value={outputValue}
                    onValueChange={(name) => set("local_output", name === DEFAULT_OUTPUT ? "" : name)}
                  >
                    <SelectTrigger className="w-full bg-muted"><SelectValue placeholder="Saved output not connected" /></SelectTrigger>
                    <SelectContent>
                      {state.outputs.map((o) => (
                        <SelectItem key={o.name || DEFAULT_OUTPUT} value={o.name || DEFAULT_OUTPUT}>{o.description}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              )}
            </div>
          </Module>

          <Module index="03" title="Behavior">
            <Field label="Playback delay">
              <div className="flex items-center gap-3 rounded-md border border-border bg-muted px-3 py-2.5">
                <input
                  type="range" min={0} max={3} step={0.1}
                  aria-label="Playback delay in seconds"
                  value={config.playback_delay_seconds}
                  onChange={(e) => set("playback_delay_seconds", Number(e.target.value))}
                  className="caspr-range flex-1"
                  style={{ "--fill": `${(config.playback_delay_seconds / 3) * 100}%` } as CSSProperties}
                />
                <span className="w-10 text-right font-mono text-[12px] text-steel">{config.playback_delay_seconds.toFixed(1)}s</span>
              </div>
            </Field>
            <ToggleRow label="Show debug error notifications" checked={config.debug_notifications} onChange={(v) => set("debug_notifications", v)} />
            <div className="flex items-center justify-between px-1 pt-1 text-[13px] text-steel">
              Overlay shortcut
              {windows ? <HotkeyField value={config.hotkey ?? ""} onCommit={(v) => set("hotkey", v)} /> : <Badge>SUPER + ALT + T</Badge>}
            </div>
          </Module>

          <Module id="quick-options" highlighted={highlight === "quick-options"} index="04" title="Quick options" action={
            <button
              className={subtle}
              disabled={config.quick_options.length >= MAX_QUICK_OPTIONS}
              onClick={() => set("quick_options", [...config.quick_options, { name: "", phrases: [] }])}
            >
              <span className="flex items-center gap-1.5"><Plus size={14} />Add category</span>
            </button>
          }>
            <p className="px-1 text-[12px] text-muted-foreground">
              Categories become chips under the message box (Alt+1–5) and /commands you can type inside a message. Each use says a random phrase in the selected voice.
              <span className="ml-1 font-mono text-fog">{config.quick_options.length}/{MAX_QUICK_OPTIONS}</span>
            </p>
            {config.quick_options.map((option, i) => (
              <QuickOptionEditor
                key={i}
                option={option}
                onChange={(next) => set("quick_options", config.quick_options.map((o, j) => (j === i ? next : o)))}
                onRemove={() => set("quick_options", config.quick_options.filter((_, j) => j !== i))}
                onSay={() => api.speak_quick(i)}
              />
            ))}
          </Module>
        </div>
      </main>

      <footer className="flex justify-between border-t border-border bg-card px-4 py-3">
        <button className={`${button} text-muted-foreground hover:bg-accent hover:text-destructive`} onClick={() => api.quit()}>Quit</button>
        <button className={primary} onClick={() => api.open_overlay()}>Open message box</button>
      </footer>
    </div>
  )
}
