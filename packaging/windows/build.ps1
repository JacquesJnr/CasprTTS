param(
    [string]$Version = '0.1.0',
    [string]$CertificateThumbprint = '',
    [string]$TimestampUrl = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($Version -notmatch '^\d+\.\d+\.\d+([.-][A-Za-z0-9.-]+)?$') { throw 'Invalid version' }
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root
function Invoke-Native([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
}
Invoke-Native python @('-c', 'import sys,struct; assert sys.platform == "win32" and sys.version_info[:2] == (3,11) and struct.calcsize("P") == 8')
# This directory contains only generated release output; do not mix versions.
if (Test-Path dist/release) { Remove-Item dist/release -Recurse -Force }
New-Item -ItemType Directory -Force build/windows, dist/release | Out-Null
Invoke-Native python @('-m', 'pip', 'check')
Invoke-Native python @('-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', 'dist', '--workpath', 'build/windows/pyinstaller', 'packaging/windows/CasprTTS.spec')
$bundle = Join-Path $root 'dist\CasprTTS'
# Enforce collection of dynamically opened resources before running native smoke.
foreach ($pattern in @('piper/espeak-ng-data', 'msvcp140.dll', 'vcruntime140_1.dll', '_sounddevice_data/portaudio-binaries/libportaudio64bit.dll',
                         'web/dist/index.html', 'webview/lib/Microsoft.Web.WebView2.Core.dll', 'webview/lib/runtimes/win-x64/native/WebView2Loader.dll',
                         'pythonnet/runtime/Python.Runtime.dll', 'clr_loader/ffi/dlls/amd64/ClrLoader.dll')) {
    if (-not (Test-Path (Join-Path "$bundle\_internal" $pattern))) { throw "Missing frozen resource: $pattern" }
}
$signTool = $null
if ($CertificateThumbprint) {
    $signTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $signTool) { throw 'Windows SDK signtool.exe missing' }
    Invoke-Native $signTool @('sign', '/sha1', $CertificateThumbprint, '/fd', 'SHA256', '/tr', $TimestampUrl, '/td', 'SHA256', "$bundle\CasprTTS.exe")
    Invoke-Native $signTool @('verify', '/pa', "$bundle\CasprTTS.exe")
}
& "$PSScriptRoot\smoke.ps1" -Executable "$bundle\CasprTTS.exe" -Report 'build/windows/frozen-smoke.json'
Invoke-Native python @('packaging/windows/inventory.py', $bundle, "$bundle\third-party")
Copy-Item docs/WINDOWS_BUILD.md "$bundle\WINDOWS_BUILD.md"
foreach ($notice in @('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'NOTICE', 'NOTICE.txt')) {
    if (Test-Path $notice) { Copy-Item $notice $bundle }
}
$inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $inno)) { throw 'Install Inno Setup 6.4.3 before building' }
$numericVersion = ($Version -split '[-]')[0]
$numericVersion = ($numericVersion -split '[.]')[0..2] -join '.'
# Microsoft's WebView2 Evergreen bootstrapper (~2 MB, downloads the runtime). The installer runs it
# only when WebView2 is missing. It is re-fetched each build, so trust its Microsoft signature, not a hash.
$webView2 = Join-Path $root 'build\windows\MicrosoftEdgeWebview2Setup.exe'
Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $webView2
$signature = Get-AuthenticodeSignature $webView2
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw "WebView2 bootstrapper signature invalid: $($signature.Status) $($signature.SignerCertificate.Subject)"
}
$innoArgs = @("/DAppVersion=$Version", "/DNumericVersion=$numericVersion", "/DBundleDir=$bundle", "/DOutputDir=$root\dist\release", "/DWebView2Bootstrapper=$webView2")
if ($CertificateThumbprint) {
    $innoArgs += '/DSignBuild=1'
    $innoArgs += "/Srelease=`"$signTool`" sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 `$f"
}
Invoke-Native $inno ($innoArgs + @('packaging/windows/CasprTTS.iss'))
$installer = "$root\dist\release\Caspr-TTS-$Version-windows-x64-setup.exe"
if ($CertificateThumbprint) { Invoke-Native $signTool @('verify', '/pa', $installer) }
Compress-Archive -Path $bundle -DestinationPath "dist/release/Caspr-TTS-$Version-windows-x64-directory.zip" -Force
Compress-Archive -Path "$bundle/third-party/*" -DestinationPath "dist/release/Caspr-TTS-$Version-dependencies.zip" -Force
Invoke-Native git @('archive', '--format=zip', "--output=dist/release/Caspr-TTS-$Version-source.zip", 'HEAD')
Copy-Item "$bundle/third-party/dependencies.json" dist/release/dependencies.json
Get-ChildItem dist/release -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object {
    "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant())  $($_.Name)"
} | Set-Content dist/release/SHA256SUMS.txt -Encoding ascii
