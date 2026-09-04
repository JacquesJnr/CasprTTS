# Caspr TTS

A keyboard-first TTS message box for Omarchy. It speaks queued messages through
a PipeWire virtual microphone and, by default, mirrors them to your headphones.

## Prototype behavior

- `SUPER + ALT + T` opens or refocuses one centered message box.
- Enter or **Send** queues the text, clears it, and immediately hides the box.
- Escape clears and hides the box.
- Up/Down browse the last 25 messages from the current app session only.
- Messages are spoken in order, with a configurable 0.5-second default delay.
- The virtual microphone appears as **QuickTTS_Microphone** in Discord
  (`quick_tts_mic` internally).
- Errors produce desktop notifications in debug mode and are silent otherwise.
- The application is started manually and remains active after Settings closes.

## Requirements

- Python 3.11+
- GTK 4 and PyGObject
- PipeWire with its PulseAudio compatibility layer (`pactl`)
- PulseAudio utilities (`pactl`, `paplay`) backed by PipeWire
- [Piper](https://github.com/OHF-Voice/piper1-gpl) and a compatible `.onnx`
  voice model with its neighboring `.onnx.json` file

## Run from the repository

```bash
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e . -r requirements-dev.txt -r requirements-tts.txt
.venv/bin/quick-tts-mic
```

The repository is currently set up this way already. `--system-site-packages`
lets the virtual environment use Omarchy's system-provided GTK/PyGObject while
keeping Piper and test tooling local to this project.

Choose the Piper `.onnx` model in Settings, then select
**QuickTTS_Microphone** as Discord's input device. Use **Open message box** to
test before installing the shortcut.

For this development checkout, `en_GB-alan-medium` is downloaded into the
ignored `data/voices/` directory and is discovered automatically. It is a
temporary male English prototype voice, not a replacement for Microsoft James.
The checkout also includes the `en_GB-jenny_dioco-medium` model, shown in Caspr
as Jenny with Irish female voice metadata, plus `en_US-amy-medium`, shown as Amy
with American female voice metadata. `en_US-hfc_male-medium` is shown as Dan
with American male voice metadata.

## Omarchy shortcut

First run `omarchy menu keybindings --print` and confirm `SUPER + ALT + T` is
unused. Then add this to `~/.config/hypr/bindings.lua`, replacing the repository
path if needed:

```lua
o.bind("SUPER + ALT + T", "Caspr TTS", "/home/jacq/Work/quick-tts-mic/scripts/quick-tts-overlay")
```

Validate the change:

```bash
hyprctl reload
hyprctl configerrors
```

If the shortcut is already assigned, add `hl.unbind("SUPER + ALT + T")` before
the new binding and note what it previously did.

This development checkout installs an app-menu entry named **Caspr TTS** in
`~/.local/share/applications/` and binds the overlay shortcut in the user's
Omarchy `bindings.lua`. Both launch the project-local virtual environment.

## Current prototype limits

- Piper/model installation is not automated yet.
- The virtual microphone exists while the application runs.
- Shortcut editing is manual for this first slice.
- Live PipeWire and Hyprland behavior must be tested inside the desktop session.
