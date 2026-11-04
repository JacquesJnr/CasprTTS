Type a message, press Enter, and Caspr TTS speaks it into Discord (or any app that
takes a microphone), in a Microsoft or Piper voice.

## Install

1. Download **`Caspr-TTS-…-windows-x64-setup.exe`** below and run it.
2. The installer isn't code-signed, so Windows SmartScreen asks first: choose
   **More info → Run anyway**. It installs for your account only (no admin needed) and
   adds Microsoft Edge WebView2 if your PC doesn't have it.
3. Optional: tick **Start Caspr TTS when I sign in** to keep it in the notification area.

## Set up Discord

- **Stereo Mix** (many desktops): enable it in Sound settings → More sound settings →
  Recording (show disabled devices). In Caspr, set **Message output** to the speakers it
  records; in Discord, set the input device to **Stereo Mix**.
- **No Stereo Mix?** (common on laptops) Install the free
  [VB-CABLE](https://vb-audio.com/Cable/). In Caspr, set **Message output** to
  **CABLE Input**; in Discord, set the input device to **CABLE Output**.

## Use it

- **Ctrl+Alt+T** opens the message box (change it in Settings). Enter speaks; Escape closes.
- **Voices:** use the Microsoft voices in Windows (add more, such as James, in Windows
  Settings → Time & language → Speech), or add Piper voices you
  [listen to here](https://rhasspy.github.io/piper-samples/) via Settings →
  **Open voices folder**. No voice models are included.
- **Quick options:** set up phrases in Settings; say a random one with a chip,
  **Alt+1–5**, or `/name` inside a message.
- Up/Down recall earlier messages; the tray icon has Open message box, Settings and Quit.

More help, including where the log file lives:
[Windows user guide](https://github.com/JacquesJnr/CasprTTS/blob/main/docs/WINDOWS_USER_GUIDE.md).

## Files

| File | What it is |
| --- | --- |
| `…-windows-x64-setup.exe` | The installer, **this is the one you want** |
| `…-windows-x64-directory.zip` | The same app without an installer |
| `…-dependencies.zip`, `dependencies.json` | Licences of bundled components |
| `…-source.zip` | Source code (GPL-3.0) |
| `SHA256SUMS.txt` | Checksums for the files above |
