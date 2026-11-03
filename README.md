![CasprTTS](docs/Banner.png)

A keyboard-first text-to-speech message box for Linux. Type a message, press
Enter, and Caspr speaks it through a PipeWire virtual microphone that Discord
(or any other app) can use as an input. By default you hear it in your
headphones too.

![Caspr message box with a highlighted /greeting command and quick option chips](docs/screenshots/overlay.png)

## Features

**Message box**

- A global shortcut opens a compact floating message box. Enter speaks and
  hides it; Escape clears and hides it.
- Messages are spoken in order, with a configurable delay (0.5 s by default).
- Up/Down browse the last 25 typed messages from the current session (kept as
  typed, so a resent `/command` picks a fresh phrase).
- A voice button switches between voices on the spot. Each voice shows its
  flag and a ♂/♀ glyph.
- **Quick options**: up to five chips under the input. Click one, or press
  `Alt+1`–`Alt+5`, to say a random phrase from that category. The round **+**
  chip opens Settings at the Quick options section.
- **Slash commands**: type `/greeting` (any category name, lowercase, spaces as
  hyphens) inside a message and it is replaced by a random phrase from that
  category when spoken, e.g. `/greeting everyone` → "Hey everyone". Known
  commands are highlighted as you type.
- **Command menu**: typing `/` at the start of a word lists your categories
  above the input. `↑`/`↓` and Enter or Tab insert one; Escape or Backspace
  closes the menu.

| Slash command menu | Voice switcher |
| --- | --- |
| ![Command menu listing /greeting, /brb and /good-luck above the input](docs/screenshots/slash-menu.png) | ![Voice menu with flags and male/female glyphs](docs/screenshots/voice-menu.png) |

**Settings**

- **Piper voice**: four English voices with friendly names (Alan, Jenny, Amy,
  Dan) plus any custom `.onnx` model. **Sample voice** plays "I love
  text-to-speech" in your headphones only; samples never reach the virtual
  microphone.
- **Audio**: a volume knob (mouse, arrow keys or scroll wheel; 0% mutes),
  headphone monitoring on/off, and a choice of headphone output.
- **Behavior**: playback delay and debug error messages.
- **Quick options**: add, rename and delete categories, with one phrase per
  line. Each shows its `/command`, and ▶ says a random phrase right away.
- Settings save automatically as you change them, and voice changes stay in
  sync between Settings and the message box.
- A **Microsoft voices** preference is saved for the upcoming Windows release
  (see below).

| Voices, audio and behavior | Quick options |
| --- | --- |
| ![Settings: voices, volume knob, audio and behavior](docs/screenshots/settings.png) | ![Settings: quick option categories with phrases and /commands](docs/screenshots/settings-quick-options.png) |

Caspr keeps running in the background after you close its windows, so the
virtual microphone stays available until you choose **Quit**.

## Requirements

- Linux with PipeWire and its PulseAudio compatibility layer (`pactl`, `paplay`)
- Python 3.11+
- PyGObject and WebKitGTK 4.1 (usually packaged as `python-gobject` /
  `python3-gi` and `webkit2gtk-4.1` / `libwebkit2gtk-4.1`)
- Node.js, to build the interface
- [Piper](https://github.com/OHF-Voice/piper1-gpl) and at least one `.onnx`
  voice model with its neighboring `.onnx.json` file

## Install and run

```bash
git clone https://github.com/JacquesJnr/CasprTTS.git
cd CasprTTS
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[web]' -r requirements-tts.txt
npm --prefix web install
npm --prefix web run build
.venv/bin/quick-tts-mic            # Settings
.venv/bin/quick-tts-mic overlay    # message box
```

`--system-site-packages` lets the virtual environment use your system's
PyGObject while keeping Piper and the other Python dependencies local to the
project.

Then select **QuickTTS_Microphone** as the input device in Discord (or your
other app), and use **Open message box** in Settings to try it.

### Voices

Download Piper voices from
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) and put each
`.onnx` file and its `.onnx.json` file in `data/voices/`. They are discovered
automatically. These four get friendly names and glyphs in the interface:

| Model | Shown as |
| --- | --- |
| `en_GB-alan-medium` | 🇬🇧 Alan, British male |
| `en_GB-jenny_dioco-medium` | 🇬🇧 Jenny, Irish female |
| `en_US-amy-medium` | 🇺🇸 Amy, American female |
| `en_US-hfc_male-medium` | 🇺🇸 Dan, American male |

Any other model appears under its file name as a custom voice.

## Global shortcut

Bind a key in your desktop environment or window manager to the launcher
script, replacing the path with your checkout:

```
/path/to/CasprTTS/scripts/quick-tts-overlay
```

The first press starts Caspr; later presses just show the message box.
For example:

- **Hyprland**: `bind = SUPER ALT, T, exec, /path/to/CasprTTS/scripts/quick-tts-overlay`
- **GNOME**: Settings → Keyboard → Custom Shortcuts
- **KDE Plasma**: System Settings → Shortcuts → Custom Shortcuts

To add Caspr to your app menu, edit the `Exec=` path in
`packaging/io.github.quickttsmic.App.desktop` and copy it to
`~/.local/share/applications/`.

## Development

Run `npm --prefix web run dev`, then start Caspr with
`CASPR_WEB_URL=http://localhost:5173` to load the live dev server instead of the
built files. Set `CASPR_WEB_DEBUG=1` to enable the web inspector. Rebuild with
`npm --prefix web run build` after changing anything in `web/`.

Install the test tools with `-r requirements-dev.txt` and run
`.venv/bin/python -m pytest`. The visual design is documented in
[STYLE_GUIDE.md](STYLE_GUIDE.md).

## Current limits

- Speech errors are shown in the app, not as desktop notifications.
- Piper and voice model installation is manual.
- The virtual microphone exists only while Caspr runs.
- The shortcut is set up in your desktop's settings, not in Caspr.

### Microsoft voice preference (Windows release preparation)

Settings includes a separate Microsoft voices dropdown. On Windows, install the
optional discovery support with `pip install '.[windows-voices]'`. It uses PyWinRT
and Windows `SpeechSynthesizer.all_voices` to list only installed voices exposed
by that API. Restart Caspr after changing installed voices to refresh the list.

The preference is saved independently of the Piper model. Missing saved voices
are not replaced automatically. On Linux, or when discovery is unavailable, the
dropdown is disabled and the saved preference is preserved.

Microsoft playback is not available yet: messages and samples still use Piper,
and audio routing is PipeWire-only. See
[the Windows release plan](docs/WINDOWS_RELEASE_PLAN.md).
