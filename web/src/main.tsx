import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { polyfillCountryFlagEmojis } from "country-flag-emoji-polyfill"
import flagFont from "country-flag-emoji-polyfill/dist/TwemojiCountryFlags.woff2?url"

import "./index.css"

// Windows can't draw flag emoji; load a bundled flag-only font there (no-op elsewhere, no CDN).
polyfillCountryFlagEmojis("Twemoji Country Flags", flagFont)
import App from "./App.tsx"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
