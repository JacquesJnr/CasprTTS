import { SelectAIAgent } from "@/components/watermelon/select-ai-agent"
import { splitFlag, useCasprState, type Api } from "@/api"

export function Overlay({ api }: { api: Api }) {
  const { state, set, error, setError } = useCasprState(api)
  if (!state) return null

  const agents = state.voices.map((v) => {
    const [flag, name] = splitFlag(v.name)
    return { id: v.id, name, icon: <span aria-hidden>{flag}</span> }
  })

  return (
    <main className="overlay-page flex min-h-svh items-end p-4 pt-20">
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
          footer={
            <p className="mt-2.5 flex justify-between px-1 font-mono text-[11px] text-muted-foreground">
              <span className={error ? "text-destructive" : "tracking-[0.2em] text-coral"}>{error || "CASPR"}</span>
              <span>Enter speak · Esc close</span>
            </p>
          }
        />
      ) : (
        <p className="rounded-xl bg-card p-4 text-sm text-muted-foreground">No Piper voices found in data/voices</p>
      )}
    </main>
  )
}
