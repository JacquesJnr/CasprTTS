# Caspr TTS — Project Spec

## Product intent

Caspr TTS lets a person who does not use a physical microphone participate
in voice chat with minimal interruption. The core interaction is:

> Press a shortcut, type one short message, press Enter, and return immediately
> to the application that was already in use.

The initial prototype targets Omarchy. The product is deliberately structured
for a later Windows 10 release for the original user of the idea.

## Primary user and problem

The primary user currently uses the Microsoft Store app **Type to Voice Chat**,
Realtek Stereo Mix, and Discord Push to Talk. Her preferred installed Windows
voice is **Microsoft James (English, Australia)**. The existing audio path works;
the painful part is repeatedly Alt-Tabbing into a full application window just
to send a short spoken message.

Caspr TTS removes that navigation cost. Audio routing and configuration are
secondary surfaces; composing a message must stay instantaneous.

## Agreed interaction

### App lifecycle

- The user launches the app manually.
- A Settings window opens on launch so the running state is obvious.
- Closing Settings leaves the app active in the background.
- The app stops only through an explicit **Quit** action.
- Autostart is out of scope for the initial prototype.

### Message overlay

- Default shortcut: `SUPER + ALT + T` on Omarchy.
- Only one overlay may exist.
- Invoking the shortcut creates or focuses the existing overlay and draft.
- The overlay is a centered, ordinary window; it is not forced always-on-top.
- The input is single-line and focused immediately.
- Enter and the **Send** button queue the message and hide the overlay at once.
- Escape discards the current draft and hides the overlay.
- Clicking away leaves the overlay and draft intact behind other windows.
- The overlay must not steal focus again after the message is submitted.

### Message history

- Every fresh invocation begins with a blank input unless an unsent draft exists.
- Up/Down navigate the latest 25 submitted messages.
- History is memory-only and disappears when the app quits.
- No message contents are persisted to disk.

### Speech and queue behavior

- The Omarchy prototype uses Piper offline.
- Submitted messages are FIFO and never overlap.
- Playback is fire-and-forget: no stop, cancel, or clear-queue controls.
- Playback begins after a configurable delay, defaulting to `0.5` seconds.
- Delay is displayed in seconds, not milliseconds.
- The app does not automate or hold Discord's Push-to-Talk binding.

### Audio behavior

- The app manages a PipeWire virtual microphone while it is running.
- Discord consumes **QuickTTS_Microphone** (`quick_tts_mic`) as its input. This
  normal remapped source is backed by `quick_tts_sink.monitor` so clients that
  hide monitor-class sources still expose it.
- Speech also plays through headphones by default.
- Local monitoring can be disabled and its output device can be selected.
- The virtual microphone receives TTS only; a physical microphone mix is not
  required.

### Failure behavior

- Prototype/debug mode may show visible desktop notifications and retain useful
  diagnostic logs while audio behavior is being validated.
- **Production mode must have no visible failure states.** Synthesis, device, or
  routing failures are silent and must never interrupt the user's active task.
- Debug visibility must be explicitly configurable and default off in a release
  build. A local non-message-content health log may be considered later.

## Settings surface

The Omarchy prototype exposes:

- An exclusive installed-voice picker
- Local headphone monitoring on/off
- Local monitoring output device
- Playback delay in seconds
- Debug error notifications
- Current overlay shortcut
- Test/open-overlay action
- Save and Quit actions

Later iterations should support shortcut recording rather than requiring a
manual Hyprland edit.

The message overlay exposes the same installed voices through a compact
dropdown. The prototype voice set is Alan (British male, medium quality), Jenny
(Irish female, medium quality; Piper model `jenny_dioco`), and Amy (American
female, medium quality), and Dan (American male, medium quality; Piper model
`hfc_male`). Piper has no official Australian English model; the downstream
Windows version remains responsible for genuine Microsoft Australian voices.

## Visual design

- Use the Catppuccin Mocha palette shipped with Omarchy: base `#1e1e2e`,
  mantle `#181825`, crust `#11111b`, text `#cdd6f4`, and blue `#89b4fa`.
- Keep the overlay visually quiet and compact, with a single dominant input and
  one primary action.
- Use rounded, bordered surfaces rather than heavy shadows or gradients.
- Present keyboard affordances in muted text so they remain discoverable
  without competing with the message field.
- Group Settings into three cards: Voice, Audio routing, and Behavior.
- Use green only for healthy status, red only for destructive actions, and blue
  for focus and primary actions.
- Preserve legibility under Omarchy's compositor opacity and fractional display
  scaling.
- Provide a compact voice dropdown directly in the message overlay. Changing it
  updates the active default without adding another confirmation step.

## Architecture boundaries

The following concerns remain separate:

1. **Overlay and settings UI** — presentation and keyboard interaction.
2. **Speech queue** — FIFO lifecycle, timing, and error isolation.
3. **Speech engine** — text-to-audio implementation.
4. **Audio router** — virtual microphone and optional local monitor.
5. **Shortcut integration** — platform-specific global activation.
6. **Configuration** — non-message preferences only.

Platform-specific implementations must sit behind the speech, audio, and
shortcut boundaries. UI behavior and queue semantics should remain consistent.

## Downstream Windows goal

A Windows 10 release is a first-class goal, not an incidental port.

- Use installed Windows speech synthesis voices when available.
- Prefer and preserve compatibility with **Microsoft James (English, Australia)**.
- Allow selecting any installed Windows voice and playback device.
- Initially support the user's working Realtek Stereo Mix route.
- Keep room for optional VB-CABLE/VoiceMeeter support without requiring either.
- Register a configurable global hotkey using native Windows facilities.
- Ship as a small background/tray app with a normal installer.
- Preserve the same shortcut-to-overlay, Enter-to-send interaction.
- Preserve the production requirement of no visible failure states.

The Windows release may use a native Windows UI rather than sharing GTK code.
The behavioral contract and core queue model matter more than using one UI
toolkit on every platform.

## Prototype acceptance criteria

The Omarchy prototype is successful when:

1. The app starts manually and creates its virtual input.
2. Discord can select the virtual input and receive generated speech.
3. The configured shortcut opens or refocuses one centered input.
4. Enter/Send hides the input immediately and queued messages play in order.
5. Speech is heard in both Discord and headphones by default.
6. Escape, session history, output selection, and delay work as specified.
7. Debug failures are useful during testing and become silent when disabled.
8. No submitted message text is stored after shutdown.

## Explicit non-goals for the first prototype

- Automating Discord Push to Talk
- Combining a physical microphone with TTS
- Persistent message history
- Saved phrases or soundboard pads
- Cloud TTS
- Autostart
- Shipping a custom audio driver
- Polished packaging for Linux or Windows

## Open validation items

- Confirm Hyprland places the ordinary overlay acceptably near screen center.
- Confirm Discord labels and retains the PipeWire monitor source predictably.
- Measure Piper cold-start latency and decide whether a warm service is needed.
- Select a pleasant bundled/recommended prototype voice.
- Test rapid message submission while a previous message is playing.
- Verify local monitoring does not feed unrelated desktop audio into Discord.
