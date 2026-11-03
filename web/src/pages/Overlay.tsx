import { useEffect } from "react"
import { motion } from "motion/react"
import { Plus } from "lucide-react"

import { SelectAIAgent } from "@/components/watermelon/select-ai-agent"
import { GenderGlyph } from "@/components/gender-glyph"
import { flagForLanguage, splitFlag, useCasprState, type Api } from "@/api"
import { commandSlug, commandSlugs, splitCommands } from "@/commands"

export function Overlay({ api }: { api: Api }) {
  const { state, set, error, setError } = useCasprState(api)

  // Keep each chip's config index: speak_quick picks the phrase in Python.
  const chips = (state?.config.quick_options ?? [])
    .map((option, index) => ({ ...option, index }))
    .filter((o) => o.name && o.phrases.length)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const chip = e.altKey && chips[Number(e.key) - 1]
      if (!chip) return
      e.preventDefault()
      api.speak_quick(chip.index)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [api, chips])

  // Windows overlays are opaque windows (no true transparency), so keep the window hugging the
  // card plus any open menu; Python grows it upward with the bottom edge fixed.
  const windows = state?.platform === "windows"
  useEffect(() => {
    if (!windows) return
    let last = 0
    const fit = () => {
      const main = document.querySelector("main")
      if (!main) return
      const rects = [...main.querySelectorAll("*")].map((el) => el.getBoundingClientRect()).filter((r) => r.height > 0)
      if (!rects.length) return
      const height = Math.ceil(Math.max(...rects.map((r) => r.bottom)) - Math.min(...rects.map((r) => r.top)))
      if (Math.abs(height - last) > 1) {
        last = height
        api.fit_overlay(height)
      }
    }
    // Re-measure after DOM changes and once more when menu animations settle.
    const schedule = () => {
      requestAnimationFrame(fit)
      setTimeout(fit, 350)
    }
    const observer = new MutationObserver(schedule)
    observer.observe(document.body, { childList: true, subtree: true })
    schedule()
    return () => observer.disconnect()
  }, [api, windows])

  if (!state) {
    return error ? (
      <main className="overlay-page flex min-h-svh items-end p-4">
        <p role="alert" className="w-full rounded-xl border border-destructive/40 bg-card p-4 text-[13px] text-destructive">{error}</p>
      </main>
    ) : null
  }
  const known = commandSlugs(state.config.quick_options)

  // On Windows with Microsoft voices selected, the switcher lists those instead of Piper models.
  const microsoft = state.platform === "windows" && state.config.speech_provider === "microsoft"
  const agents = microsoft ? state.microsoft.voices.map((v) => ({
    id: v.id,
    name: v.name.replace(/^Microsoft\s+/, ""),
    icon: (
      <span className="flex items-center gap-0.5">
        <span aria-hidden>{flagForLanguage(v.language) || "🔊"}</span>
        <GenderGlyph gender={v.gender} size={12} />
      </span>
    ),
  })) : state.voices.map((v) => {
    const [flag, name] = splitFlag(v.name)
    return {
      id: v.id,
      name,
      icon: (
        <span className="flex items-center gap-0.5">
          <span aria-hidden>{flag}</span>
          <GenderGlyph gender={v.gender} size={12} />
        </span>
      ),
    }
  })

  return (
    <main className={`overlay-page flex min-h-svh items-end ${windows ? "" : "p-4"}`}>
      {agents.length ? (
        <SelectAIAgent
          agents={agents}
          selectedId={microsoft ? state.config.microsoft_voice_id : state.config.model_path}
          onSelectAgent={(id) => set(microsoft ? "microsoft_voice_id" : "model_path", id)}
          onSendMessage={(text) => {
            setError("")
            api.speak(text)
          }}
          onEscape={() => api.close()}
          slashOptions={chips.map((c) => ({
            id: commandSlug(c.name),
            label: c.name,
            detail: `${c.phrases.length} phrase${c.phrases.length === 1 ? "" : "s"}`,
          }))}
          slashEmpty="No quick options yet · press + to add one"
          onHistory={(direction, current) =>
            direction === "previous" ? api.history_previous(current) : api.history_next()
          }
          renderValue={(text) =>
            splitCommands(text, known).map((part, i) =>
              part.command ? <span key={i} className="text-primary">{part.text}</span> : part.text
            )
          }
          footer={
            <>
              <div role="group" aria-label="Quick options" className="mt-2 flex flex-wrap items-center gap-1.5 px-0.5">
                {chips.map((chip, i) => (
                  <motion.button
                    key={chip.index}
                    whileTap={{ scale: 0.94 }}
                    title={`Say a random ${chip.name.toLowerCase()} (Alt+${i + 1}) · or type /${commandSlug(chip.name)}`}
                    onClick={() => {
                      setError("")
                      api.speak_quick(chip.index)
                    }}
                    className="flex items-center gap-1.5 rounded-full border border-input bg-muted px-2.5 py-1 text-[12px] text-steel outline-none transition hover:border-primary/60 hover:text-foreground hover:shadow-glow-sm focus-visible:border-primary/70 focus-visible:shadow-glow"
                  >
                    <span className="font-mono text-[10px] text-fog">{i + 1}</span>
                    {chip.name}
                  </motion.button>
                ))}
                <motion.button
                  whileTap={{ scale: 0.9 }}
                  title="Edit quick options"
                  aria-label="Edit quick options"
                  onClick={() => api.open_settings("quick-options")}
                  className="flex size-[26px] items-center justify-center rounded-full border border-input bg-muted text-muted-foreground outline-none transition hover:border-primary/60 hover:text-primary hover:shadow-glow-sm focus-visible:border-primary/70 focus-visible:shadow-glow"
                >
                  <Plus size={13} strokeWidth={2.5} />
                </motion.button>
              </div>
              <p className="mt-2 flex justify-between px-1 font-mono text-[11px] text-muted-foreground">
                <span className={error ? "text-destructive" : "text-fog"}>{error || "caspr"}</span>
                <span>Enter speak · ↑↓ history{chips.length > 0 && ` · Alt+${chips.length > 1 ? `1–${chips.length}` : 1} quick`} · Esc close</span>
              </p>
            </>
          }
        />
      ) : (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">No voices found · add one in Settings</p>
      )}
    </main>
  )
}
