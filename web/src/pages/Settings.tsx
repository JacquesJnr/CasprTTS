import { useState, type CSSProperties, type ReactNode } from "react"
import { motion } from "motion/react"
import { Mic } from "lucide-react"

import { KnobSlider } from "@/components/watermelon/knob-slider"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { splitFlag, useCasprState, type Api } from "@/api"

// Radix Select reserves "" for "no value", so the default output gets a sentinel.
const DEFAULT_OUTPUT = "__default__"

function Module({ index, title, action, children }: {
  index: string; title: string; action?: ReactNode; children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-3 shadow-lift">
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

export function Settings({ api }: { api: Api }) {
  const { state, set, error } = useCasprState(api)
  const [sampling, setSampling] = useState(false)
  if (!state) return null
  const { config } = state
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

          <Module index="01" title="Piper voice" action={
            <button
              className={subtle}
              disabled={!state.voices.length || sampling}
              title="Hear “I love text-to-speech” through headphones only"
              onClick={sample}
            >
              {sampling ? "Sampling…" : "Sample voice"}
            </button>
          }>
            <div role="radiogroup" aria-label="Piper voice" className="grid grid-cols-2 gap-2">
              {state.voices.map((v) => {
                const [flag, name] = splitFlag(v.name)
                const active = v.id === config.model_path
                return (
                  <button
                    key={v.id}
                    role="radio"
                    aria-checked={active}
                    onClick={() => set("model_path", v.id)}
                    className="relative flex items-center gap-3 rounded-md border border-border bg-muted px-3 py-2.5 text-left outline-none hover:bg-accent/40 focus-visible:shadow-glow"
                  >
                    {active && (
                      <motion.span
                        layoutId="voice-active"
                        transition={{ type: "spring", stiffness: 500, damping: 35 }}
                        className="absolute -inset-px rounded-md border border-primary/70 bg-primary/[0.04] shadow-glow"
                      />
                    )}
                    <span className="relative text-xl" aria-hidden>{flag}</span>
                    <span className="relative flex flex-col">
                      <span className="text-[13px] font-[510]">{name}</span>
                      <span className="text-[12px] text-muted-foreground">{v.detail}</span>
                    </span>
                  </button>
                )
              })}
            </div>

            <Field
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
            </Field>
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
              Overlay shortcut <Badge>SUPER + ALT + T</Badge>
            </div>
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
