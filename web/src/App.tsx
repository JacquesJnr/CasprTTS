import { useEffect, useState } from "react"

import { whenApiReady, type Api } from "@/api"
import { Overlay } from "@/pages/Overlay"
import { Settings } from "@/pages/Settings"

export function App() {
  const [page, setPage] = useState<{ api: Api; kind: "overlay" | "settings" }>()

  useEffect(() => {
    whenApiReady().then(async (api) => setPage({ api, kind: await api.kind() }))
  }, [])

  if (!page) return null
  return page.kind === "overlay" ? <Overlay api={page.api} /> : <Settings api={page.api} />
}

export default App
