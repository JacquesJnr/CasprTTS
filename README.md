![CasprTTS](docs/Banner.png)

A keyboard-first text-to-speech message box for Linux and Windows. Type a message,
press Enter, and Caspr speaks it into something Discord (or any other app) can use as
an input: a PipeWire virtual microphone on Linux, or Stereo Mix or a virtual cable on Windows. By
default you hear it in your headphones too.

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

<sub>Screenshots show Piper voices downloaded separately; Caspr doesn't include any voice models.</sub>

| Slash command menu | Voice switcher |
| --- | --- |
| ![Command menu listing /greeting, /brb and /good-luck above the input](docs/screenshots/slash-menu.png) | ![Voice menu with flags and male/female glyphs](docs/screenshots/voice-menu.png) |

**Settings**

- **Voice**: choose from the [voices you have](#voices): Piper voice models you
  download, and on Windows also the Microsoft voices installed in Windows. **Sample
  voice** plays "I love text-to-speech" in your headphones only; samples never reach
  Discord.
- **Audio**: a volume knob (mouse, arrow keys or scroll wheel; 0% mutes),
  headphone monitoring on/off, and a choice of headphone output.
- **Behavior**: playback delay and debug error messages.
- **Quick options**: add, rename and delete categories, with one phrase per
  line. Each shows its `/command`, and ▶ says a random phrase right away.
- Settings save automatically as you change them, and voice changes stay in
  sync between Settings and the message box.
- On Windows: a Microsoft/Piper voice switch, message and headphone outputs, and
  an editable global shortcut (see [Windows](#windows)).

| Voices, audio and behavior | Quick options |
| --- | --- |
| ![Settings: voices, volume knob, audio and behavior](docs/screenshots/settings.png) | ![Settings: quick option categories with phrases and /commands](docs/screenshots/settings-quick-options.png) |

Caspr keeps running in the background after you close its windows, so the
virtual microphone stays available until you choose **Quit**.

## Requirements (Linux)

Windows users can skip to [Windows](#windows): the installer bundles everything.

- Linux with PipeWire and its PulseAudio compatibility layer (`pactl`, `paplay`)
- Python 3.11+
- PyGObject and WebKitGTK 4.1 (usually packaged as `python-gobject` /
  `python3-gi` and `webkit2gtk-4.1` / `libwebkit2gtk-4.1`)
- Node.js, to build the interface
- [Piper](https://github.com/OHF-Voice/piper1-gpl) (installed by the command below) and
  at least one [Piper voice](#voices) you download

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

## Voices

Caspr doesn't include any voice models: you choose and download them yourself.

**Piper voices** (Linux and Windows, optional on Windows): download a voice from
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices). Each voice is a
pair of files, `<name>.onnx` and `<name>.onnx.json`; put both in the voices folder:

- Linux: `data/voices/` in your checkout
- Windows: Settings → Voice → **Piper voices** → **Open voices folder**
  (`%LOCALAPPDATA%\Caspr TTS\data\voices`)

Settings lists them automatically. Some well-known models are shown with a friendly
name, flag and ♂/♀; others appear under their file name. Each voice has its own
license and attribution; check its model card before sharing recordings.

**Microsoft voices** (Windows only): Caspr lists the voices Windows offers to apps.
Windows includes a few (for example David, Zira or Mark); add more, such as James, in
Windows Settings → Time & language → Speech → **Manage voices**, then restart Caspr.

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
- Piper voice models are not included; download the ones you want.
- Linux: the virtual microphone exists only while Caspr runs, and the shortcut is
  set up in your desktop's settings, not in Caspr.
- Windows: the installer is unsigned, and Stereo Mix sends everything on its output
  to Discord (VB-CABLE avoids that).

## Windows

Caspr also runs on Windows 10/11 (x64) with the same interface. It speaks with the
Microsoft voices installed in Windows, or with Piper voices you add (see
[Voices](#voices)), and Discord hears it via **Stereo Mix** or a virtual cable.

1. Download `Caspr-TTS-…-windows-x64-setup.exe` from
   [Releases](https://github.com/JacquesJnr/CasprTTS/releases) and run it. The build is
   **unsigned**, so Windows SmartScreen asks first: choose **More info → Run anyway**.
   It installs for your user only (no admin) and installs Microsoft Edge WebView2 if
   it is missing. Optionally tick **Start Caspr TTS when I sign in**.
2. Enable **Stereo Mix** (Sound settings → More sound settings → Recording → show
   disabled devices), set Caspr's **Message output** to the device it records, and
   select **Stereo Mix** as Discord's input. Discord then hears everything on that
   output. **No Stereo Mix?** (common on laptops) Install the free
   [VB-CABLE](https://vb-audio.com/Cable/), set **Message output** to **CABLE Input**
   and Discord's input to **CABLE Output**; Discord then hears only Caspr.
3. Press **Ctrl+Alt+T** (configurable) to open the message box; the tray icon has
   Open message box, Settings and Quit.

Full details, troubleshooting and the log file location are in the
[Windows user guide](docs/WINDOWS_USER_GUIDE.md); building the installer is covered
in [WINDOWS_BUILD.md](docs/WINDOWS_BUILD.md).

## License

Caspr TTS is free software under the [GNU General Public License v3.0](LICENSE.md)
(or later). The Windows build bundles the Piper speech engine (GPL-3.0-or-later), but
no voice models.

## Credits

- [Piper](https://github.com/OHF-Voice/piper1-gpl) speech engine (GPL-3.0-or-later).
  Piper voice models are downloaded separately and keep their own licenses.
- [Watermelon UI](https://ui.watermelon.sh) and [shadcn/ui](https://ui.shadcn.com)
  components, [Motion](https://motion.dev), [lucide](https://lucide.dev) icons.
- [Inter](https://rsms.me/inter/) and [IBM Plex Mono](https://github.com/IBM/plex)
  fonts (SIL Open Font License 1.1).
- Country flags on Windows from [Twemoji](https://github.com/jdecked/twemoji),
  © Twitter, Inc and other contributors, licensed
  [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/), via
  [country-flag-emoji-polyfill](https://github.com/talkjs/country-flag-emoji-polyfill).
- [pywebview](https://pywebview.flowrl.com/) (BSD-3-Clause),
  [pystray](https://github.com/moses-palmer/pystray) (LGPL-3.0),
  [PyWinRT](https://github.com/pywinrt/pywinrt) (MIT),
  [python-sounddevice](https://github.com/spatialaudio/python-sounddevice) and
  [PortAudio](https://www.portaudio.com/) (MIT), Microsoft Edge WebView2 and the Visual
  C++ runtime (Microsoft redistributable terms).
- Style based on Refero's "Linear" reference.

Windows installers also contain a `third-party` folder with every bundled package's
license notices.
