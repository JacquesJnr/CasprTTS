import type { QuickOption } from "@/api"

// Mirrors SLASH_COMMAND / command_slug in src/quick_tts_mic/config.py (Python expands on send).
const SLASH_COMMAND = /(?<!\S)\/([\p{L}\p{N}\p{M}_-]+)/gu

export const commandSlug = (name: string) => name.trim().toLowerCase().replace(/\s+/g, "-")

/** Slugs of categories that can expand: named and with at least one phrase. */
export const commandSlugs = (options: QuickOption[]) =>
  new Set(options.filter((o) => o.name && o.phrases.length).map((o) => commandSlug(o.name)))

/** Split text into plain and known-command segments, in order. */
export function splitCommands(text: string, known: Set<string>) {
  const parts: { text: string; command: boolean }[] = []
  let last = 0
  for (const match of text.matchAll(SLASH_COMMAND)) {
    if (!known.has(match[1].toLowerCase())) continue
    if (match.index > last) parts.push({ text: text.slice(last, match.index), command: false })
    parts.push({ text: match[0], command: true })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last), command: false })
  return parts
}
