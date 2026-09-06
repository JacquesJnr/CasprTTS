param([Parameter(Mandatory)][string]$Installer)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$Installer = (Resolve-Path $Installer).Path
$installDir = Join-Path $env:LOCALAPPDATA 'Programs\Caspr TTS'
$dataDir = Join-Path $env:LOCALAPPDATA 'Caspr TTS'
if ((Test-Path $installDir) -or (Test-Path $dataDir)) {
    throw 'Installer verification requires a disposable Windows user with no existing Caspr installation/data'
}
function Run-Setup([string]$File, [string[]]$Arguments) {
    $p = Start-Process $File -ArgumentList $Arguments -PassThru
    if (-not $p.WaitForExit(120000)) { $p.Kill(); throw 'Installer operation timed out' }
    if ($p.ExitCode -ne 0) { throw "Installer operation failed: $($p.ExitCode)" }
}
$logs = [IO.Path]::GetFullPath('build/windows')
# A lower-version installer with the same AppId exercises actual upgrade detection.
$baselineDir = Join-Path $logs 'baseline'
New-Item -ItemType Directory -Force $baselineDir | Out-Null
$bundle = (Resolve-Path 'dist/CasprTTS').Path
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" '/DAppVersion=0.0.0' "/DBundleDir=$bundle" "/DOutputDir=$baselineDir" "$PSScriptRoot\CasprTTS.iss"
if ($LASTEXITCODE -ne 0) { throw 'Baseline installer compile failed' }
Run-Setup "$baselineDir\Caspr-TTS-0.0.0-windows-x64-setup.exe" @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$logs\install.log`"")
if (-not (Test-Path "$installDir\CasprTTS.exe")) { throw 'Per-user installation missing' }
& "$PSScriptRoot\smoke.ps1" -Executable "$installDir\CasprTTS.exe" -Report "$logs\installed-smoke.json"
New-Item -ItemType Directory -Force "$dataDir\data\voices" | Out-Null
Set-Content "$dataDir\config.json" '{"packaging_sentinel":true}' -Encoding utf8
Set-Content "$dataDir\data\voices\preserve.onnx" 'User model preservation sentinel' -Encoding ascii
Set-Content "$dataDir\data\voices\preserve.onnx.json" '{}' -Encoding ascii
$preserved = @{}
Get-ChildItem $dataDir -File -Recurse | ForEach-Object { $preserved[$_.FullName] = (Get-FileHash $_.FullName).Hash }
Run-Setup $Installer @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$logs\upgrade.log`"")
& "$PSScriptRoot\smoke.ps1" -Executable "$installDir\CasprTTS.exe" -Report "$logs\upgraded-smoke.json"
foreach ($file in $preserved.Keys) {
    if ((Get-FileHash $file).Hash -ne $preserved[$file]) { throw "Upgrade changed user data: $file" }
}
if ((Get-AuthenticodeSignature $Installer).Status -eq 'Valid') {
    foreach ($signedFile in @('CasprTTS.exe', 'unins000.exe')) {
        if ((Get-AuthenticodeSignature "$installDir\$signedFile").Status -ne 'Valid') { throw "Invalid installed signature: $signedFile" }
    }
}
Run-Setup "$installDir\unins000.exe" @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$logs\uninstall.log`"")
if (Test-Path "$installDir\CasprTTS.exe") { throw 'Uninstaller left the application executable' }
foreach ($file in $preserved.Keys) {
    if ((Get-FileHash $file).Hash -ne $preserved[$file]) { throw "Uninstall changed user data: $file" }
}
Write-Output 'Install, frozen launch, version upgrade and uninstall preservation passed.'
