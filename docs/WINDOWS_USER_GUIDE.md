# Caspr TTS on Windows

Launch **Caspr TTS** from the Start menu after installing. Settings opens first.
The installer also installs Microsoft Edge WebView2 for your account if Windows
doesn't already have it (Windows 11 and updated Windows 10 usually do). The app
keeps running in the notification area after you close its windows; use its tray
icon to open the message box, open Settings or **Quit**.

## Choose a voice

In **Voice**, pick **Microsoft voices** or **Piper voices**. The two remember their
selections separately.

- **Microsoft voices** lists the voices Windows exposes to apps (for example
  James, Hazel, David, Zira), each with its flag and ♂/♀. A saved voice that is
  later removed stays saved but won't speak until you choose an available one.
- **Piper voices**: use **Open voices folder**, add an `.onnx` file and its
  matching `.onnx.json`, then switch back to Settings; the list refreshes when the
  window regains focus. Models are not bundled or downloaded automatically. Keep
  each model's license and attribution.

## Route speech to Discord (Stereo Mix)

1. In Windows Sound settings → **Recording**, enable **Stereo Mix** (show disabled
   devices if needed).
2. In Caspr **Audio**, set **Message output** to the playback device Stereo Mix
   records, usually **Speakers (Realtek(R) Audio)**.
3. In Discord, set the input device to **Stereo Mix**. Keep using your normal Push
   to Talk.

Stereo Mix records *everything* that output plays, so Discord also hears game,
browser and system sounds from it. Caspr never switches to the system default if
the selected device disappears; reconnect it or choose another output in Settings.

To hear speech yourself, turn on **Hear speech in headphones** and choose a
**Headphone output** that is a *different* device (for example USB or Bluetooth
headphones). **Sample voice** only plays there, so samples never reach Stereo Mix;
it stays disabled until a separate headphone output is chosen.

## Type and speak

The default shortcut is **Ctrl+Alt+T**. Change it in **Behavior → Overlay
shortcut** using Ctrl, Alt and/or Shift plus a letter, digit or F1–F24
(Windows-key combinations are not supported). If another app already uses the
shortcut, a tray notification says so and the tray icon stays usable.

- **Enter** speaks, then clears and hides the box. **Escape** clears and hides it.
- **Up/Down** browse the last 25 typed messages from this session (memory only).
- Quick option chips (**Alt+1**–**Alt+5**) and `/commands` say a random phrase
  from a category you set up in **Quick options**; typing `/` lists them.

Messages play in order with the voice, volume and outputs selected when you send
them. The delay is measured from sending, and playback adds 0.5 seconds of silence
to wake an idle output. A failed message does not stop the rest of the queue.
Turn on **Show debug error notifications** to see speech, device and routing errors
in the message box and Settings. Launching Caspr again just opens the running copy's
window; **Quit** stops speech and releases the shortcut.

## Files and troubleshooting

Settings: `%LOCALAPPDATA%\Caspr TTS\config.json`.
Models: `%LOCALAPPDATA%\Caspr TTS\data\voices`.
Speech stays in memory; the app does not save messages or speech recordings.
Diagnostic probe WAVs are files you asked for; delete them after testing.

If playback fails, check the selected output and voice. Caspr reports the failure
instead of picking another output or voice. If James is missing, run the
[feasibility probes](WINDOWS_FEASIBILITY.md) to see what Windows exposes.

Build and installer instructions are in [WINDOWS_BUILD.md](WINDOWS_BUILD.md).
