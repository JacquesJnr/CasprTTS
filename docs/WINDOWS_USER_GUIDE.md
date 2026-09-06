# Caspr TTS on Windows

Launch **Caspr TTS** from the Start menu after installing. Settings opens first.
The app runs in the notification area after you close its windows; use its tray
menu to open Settings, open the message box, or Quit.

## Choose speech and outputs

1. Choose **Microsoft** as the speech provider and select one of the installed
   Microsoft voices, or choose **Piper** and select your local model. The two voice
   lists remember their selections independently. Missing saved voices stay saved
   but will not speak until you explicitly choose an available voice.
2. For Piper, use **Open voices folder**, add an `.onnx` file and its matching
   `.onnx.json`, then **Refresh voices / outputs**. Models are not bundled or
   downloaded automatically. Keep the model's license and attribution.
3. Choose **Message output**. Caspr never switches to the system default if the
   selected device disappears. Reconnect or choose another device in Settings.
4. If needed, choose a separate **Monitor / preview output** and enable monitoring
   to hear sent messages locally. Identical message/monitor IDs play only once.

For the existing Realtek route, message output is the Realtek playback device
captured by **Stereo Mix**, and Discord's input is **Stereo Mix**. This can capture
other sounds on that output. If there is no isolated headphone output, leave
previews disabled.

For optional VB-CABLE, message output is **CABLE Input** and Discord input is
**CABLE Output**. Choose headphones for monitoring/previews. Caspr does not install
a virtual audio driver, change Windows defaults, mix a physical microphone, or
press Discord's Push to Talk key. Keep using your normal PTT workflow.

## Type and speak

The default shortcut is **Ctrl+Alt+T**. It is configurable in Settings; a conflict
shows a message and leaves the tray usable. Use Ctrl, Alt and/or Shift plus a letter,
digit or F1–F24. Windows-key combinations are not supported.

- **Enter** queues the text and hides/clears the box.
- **Escape** clears and hides without sending.
- **Up/Down** browse the last 25 messages held only in memory for this session.

Messages use the provider, voice, volume and outputs selected when submitted. They
play in order. The configurable delay is measured from submission, and playback
adds 0.5 seconds of silence to wake an idle output. Runtime speech, device and
routing errors are silent by default. Enable **Show speech, device and routing
errors** in Settings when diagnosing a failure; visible warnings do not include
spoken text. Shortcut conflicts remain visible while editing the shortcut. A
failed item does not stop the rest of the queue. Quit discards queued work.

Launching a second copy opens the running copy's message box. Closing Settings
keeps the app running; **Quit** stops the worker and releases the shortcut.

## Voice samples and privacy

Samples say “I love text-to-speech” through the preview output, independently of
message monitoring. Samples start disabled. To enable them:

1. Select different message and preview outputs.
2. Record your actual Discord input while playing nonprivate test audio through
   the preview output. Check that the recording contains none of that audio.
3. Only after confirming this, check **I verified preview isolation for this session**.

This checkbox is your confirmation of the external test. Device names cannot prove
isolation, and Windows Listen or other mixers may route headphones into capture.
Uncheck it before changing those mixers. Verification expires on restart, output
selection changes, detected device changes, and power/suspend/resume notifications.
Unchecking also revokes queued samples. A disconnected preview never falls back.

## Files and troubleshooting

Settings: `%LOCALAPPDATA%\Caspr TTS\config.json`.
Models: `%LOCALAPPDATA%\Caspr TTS\data\voices`.
Speech stays in memory; the app does not save message history or temporary speech
recordings. Diagnostic probe WAVs are explicitly requested files you should delete
after testing. Settings save automatically and are kept separate from program files.

Use **Refresh voices / outputs** after installing a voice or reconnecting hardware.
If playback fails, check the exact selected output, voice/model pair and try the
other 44.1/48 kHz sample rate. Caspr reports failure instead of choosing another
output or provider. Selecting Microsoft does not guarantee that Windows exposes
Microsoft James; consult the [feasibility probes](WINDOWS_FEASIBILITY.md).

Build and installer instructions are in [WINDOWS_BUILD.md](WINDOWS_BUILD.md).
Windows 10/11 hardware acceptance, James and Discord route measurements must be
recorded separately from automated build results.
