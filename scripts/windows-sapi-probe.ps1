# Optional installed-SAPI diagnostic for a voice absent from WinRT.
# Never changes voice registration or speaks to the default audio device.
param([string]$VoiceId, [string]$Wav)
$ErrorActionPreference = 'Stop'
$voice = $null
$stream = $null
try {
    $voice = New-Object -ComObject SAPI.SpVoice
    $tokens = @($voice.GetVoices() | ForEach-Object { $_ })
    if (-not $VoiceId) {
        @($tokens | ForEach-Object {
            @{ id = $_.Id; name = $_.GetDescription(); language = $_.GetAttribute('Language') }
        }) | ConvertTo-Json -Depth 4
        exit 0
    }
    $matches = @($tokens | Where-Object { $_.Id -ceq $VoiceId })
    if ($matches.Count -ne 1) { throw 'Voice ID must match exactly one installed SAPI voice. No fallback.' }
    if (-not $Wav) { throw 'Supply -Wav for synthesis.' }
    if (Test-Path -LiteralPath $Wav) { throw 'Output already exists; choose a new WAV path.' }
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Open([IO.Path]::GetFullPath($Wav), 3, $false)
    $voice.Voice = $matches[0]
    $voice.AudioOutputStream = $stream
    [void]$voice.Speak('I love text-to-speech', 0)
    $stream.Close()
    @{ ok = $true; wav = $Wav; provider = 'SAPI diagnostic only' } | ConvertTo-Json
} catch {
    Write-Error $_
    exit 1
} finally {
    if ($stream) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($stream) }
    if ($voice) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($voice) }
}
