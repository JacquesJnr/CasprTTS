# CASPR · midnight command center

Based on Refero's **Linear** style ("Midnight Command Center": a dark, layered interface lit by precise accents, like a high-tech control panel). Depth comes from layered near-black surfaces and thin borders, not heavy shadows. One accent, neon lime, marks the primary action, active states and focus — and only those carry a subtle lime glow.

Tokens live in `web/src/index.css`. The GTK shell (`assets/style.css`) still uses the previous pedal palette.

## Palette

| Role | Color | Token | Use |
| --- | --- | --- | --- |
| Pitch Black | `#08090a` | `--background`, `--muted` | Window canvas; nested wells (inputs, voice cards, toggle rows) |
| Graphite | `#0f1011` | `--card` | Modules, message shell, footer |
| Deep Slate | `#161718` | `--popover`, `--secondary` | Menus, knob face, secondary buttons |
| Charcoal Grey | `#23252a` | `--border`, `--accent` | Card borders, hover fill |
| Muted Ash | `#323334` | `--input` | Control outlines |
| Gunmetal | `#383b3f` | `--gunmetal` | Badges, off switch track, unlit knob ticks |
| Porcelain | `#f7f8f8` | `--foreground` | Primary text |
| Light Steel | `#d0d6e0` | `--steel` | Field labels, values |
| Storm Cloud | `#8a8f98` | `--muted-foreground` | Help text, placeholders |
| Fog Grey | `#62666d` | `--fog` | Module indices, metadata |
| Neon Lime | `#e4f222` | `--primary`, `--ring` | Primary action, active selection, focus, lit knob ticks |
| Warning Red | `#eb5757` | `--destructive` | Errors, Quit hover |

Never introduce a second saturated color; lime keeps its singular role.

## Glow

`shadow-glow` (1 px lime ring + 14 px soft lime bloom) and `shadow-glow-sm` apply only to lime items: the primary button, the selected voice, checked switches, the focused input, the knob's lit ticks and pointer, and the range thumb. Neutral elements use `shadow-lift`, a barely-there stacked drop shadow.

## Shape and spacing

- Controls, wells and buttons use 6 px corners (`rounded-md`); badges 4 px; modules and the message shell 12 px (`rounded-xl`).
- Compact density: 8 px element gaps, 12 px module padding, 12 px between modules.
- The message window is a compact 560 px surface: voice button, message entry, speak button, then keyboard hints. Enter submits speech.

## Type and interaction

Inter Variable (bundled) for all UI, tracking −0.01 em; headings use weight 510–590, never bold. IBM Plex Mono (bundled, substitute for Berkeley Mono) for indices, badges, shortcuts and numeric values. Body 13 px, help 12 px, module titles 15 px, wordmark 20 px.

Keep visible keyboard focus (lime glow) on every control. Volume is a 270° knob with lime-lit ticks, arrow/scroll-wheel control and a numeric readout. Settings apply and persist as controls change; there is no Save button. Voice selection stays synchronized between Settings and the message window.
