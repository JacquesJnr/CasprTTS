import { useEffect } from "react"
import { motion } from "motion/react"
import { Plus } from "lucide-react"

import { SelectAIAgent } from "@/components/watermelon/select-ai-agent"
import { splitFlag, useCasprState, type Api } from "@/api"
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

  if (!state) return null
  const known = commandSlugs(state.config.quick_options)

  const agents = state.voices.map((v) => {
    const [flag, name] = splitFlag(v.name)
    return { id: v.id, name, icon: <span aria-hidden>{flag}</span> }
  })

  return (
    <main className="overlay-page flex min-h-svh items-end p-4">
      {agents.length ? (
        <SelectAIAgent
          agents={agents}
          selectedId={state.config.model_path}
          onSelectAgent={(id) => set("model_path", id)}
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
                <span>Enter speak{chips.length > 0 && ` · Alt+${chips.length > 1 ? `1–${chips.length}` : 1} quick`} · Esc close</span>
              </p>
            </>
          }
        />
      ) : (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">No Piper voices found in data/voices</p>
      )}
    </main>
  )
}
