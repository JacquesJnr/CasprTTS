# Windows release plan

Status: planning only. The current runnable app remains the Linux/GTK/PipeWire prototype.
Branch: `feature/windows-release`.

## Product contract

- Global shortcut opens or refocuses a compact single-line message window.
- Enter queues speech and hides the window immediately; Escape dismisses it.
- Session history stays in memory. Settings apply and persist automatically.
- Preserve the cyberfunky visual language in `STYLE_GUIDE.md`.
- Voice samples say “I love text-to-speech”, respect volume, and play locally only.
- Piper voices are added by dropping `.onnx` and matching `.onnx.json` files into
  the app's `data/voices/` folder, then restarting. No import GUI.
- Discover installed Microsoft voices through Windows APIs, including Microsoft
  James (English, Australia) when available. Do not parse or copy APM/BEP/INI
  voice resources; leave Windows in charge of those installed resources.

## Implementation stages

1. **Validate Windows speech access.** Build a small Windows-only probe that
   enumerates `Windows.Media.SpeechSynthesis.SpeechSynthesizer.AllVoices`, selects
   James by its returned ID, and generates an audio stream. Record the Windows
   version and voices actually exposed. Evaluate SAPI separately if needed.
2. **Separate voice identity from model paths.** Represent a voice by provider,
   stable ID, display name, locale, and optional Piper model path. Migrate current
   `model_path` settings without losing the selected voice. Both engines produce
   audio consumed by the playback layer, rather than playing directly.
3. **Validate audio routing.** Add Windows output-device enumeration and playback.
   Test the existing Realtek Stereo Mix setup and optional virtual cable routing.
   Explicitly separate message and sample destinations. Stereo Mix can capture
   local samples if it records the same output: local-only routing cannot be
   promised in that configuration. Require a separate preview endpoint or disable
   previews when isolation cannot be established. Do not ship a custom driver.
4. **Choose the Windows shell.** Compare packaged GTK with a native Windows UI
   after the speech/routing probes. Implement a single instance, configurable
   native global hotkey, tray lifecycle, and the existing overlay interactions.
5. **Package and validate.** Produce a Windows build with a documented writable
   voice folder, bundled voice manifest and attribution, and preserved user-added
   voices during upgrades. Confirm supported Windows versions, installer versus
   portable distribution, dependency redistribution, and signing before release.
6. **Release candidate.** Build on a Windows runner, run automated checks and
   manual hardware tests, prepare checksums and release notes, and publish a
   prerelease only after the executable artifacts have been validated.

## Acceptance checks

- James and a Piper voice synthesize through their respective engines.
- Switching voices, volume, delay, output, and monitoring persists automatically.
- Queued messages remain ordered and never overlap; errors do not kill the queue.
- Sample audio never reaches the Discord recording endpoint, including when
  monitoring is disabled or the default playback device changes.
- A disconnected preview endpoint fails closed, without rerouting to the call.
- Hotkey focus, Enter, Escape, and history work while another app is foreground.
- Adding a Piper model pair discovers it after restart without editing code.
- Production debug notifications default off; no message text is persisted.
- Installation, upgrade, and removal are tested on a clean Windows machine.

## Decisions still needed

- Minimum supported Windows version and CPU architectures.
- Native versus GTK shell, guided by the working Windows probes.
- Audio setup that guarantees private samples alongside the user's Discord route.
- Final bundled Piper voices and redistribution terms for each selected model.
- Portable versus installer packaging, writable voice location, and signing.

## API references

- [Windows SpeechSynthesizer](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer)
- [Installed voice enumeration](https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer.allvoices)
