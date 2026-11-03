import { Mars, Venus } from "lucide-react"

/** ♂/♀ beside a voice's flag; lucide icons so Windows fonts can't swap in colour emoji. */
export function GenderGlyph({ gender, size = 13 }: { gender?: string; size?: number }) {
  if (gender !== "male" && gender !== "female") return null
  const Icon = gender === "male" ? Mars : Venus
  return (
    <Icon size={size} strokeWidth={2.25} role="img" aria-label={`${gender} voice`} className="shrink-0 text-muted-foreground">
      <title>{gender === "male" ? "Male voice" : "Female voice"}</title>
    </Icon>
  )
}
