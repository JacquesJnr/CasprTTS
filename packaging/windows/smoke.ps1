param([Parameter(Mandatory)][string]$Executable, [Parameter(Mandatory)][string]$Report)
$ErrorActionPreference = 'Stop'
$Executable = (Resolve-Path $Executable).Path
$Report = [IO.Path]::GetFullPath($Report)
New-Item -ItemType Directory -Force (Split-Path $Report) | Out-Null
Remove-Item $Report -ErrorAction SilentlyContinue
# No developer Python paths should make a broken bundle pass.
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONPATH = ''
    $process = Start-Process -FilePath $Executable -ArgumentList @('--smoke-test', '--smoke-report', "`"$Report`"") -WorkingDirectory $env:TEMP -PassThru
    if (-not $process.WaitForExit(120000)) {
        $process.Kill()
        throw 'Frozen smoke test timed out after 120 seconds'
    }
    if ($process.ExitCode -ne 0) { throw "Frozen smoke test exited $($process.ExitCode)" }
    if (-not (Test-Path $Report)) { throw 'Frozen smoke report missing' }
    $result = Get-Content $Report -Raw | ConvertFrom-Json
    if ($result.ok -ne $true) { throw "Smoke report did not confirm success: $(Get-Content $Report -Raw)" }
} finally {
    $env:PATH = $oldPath
    $env:PYTHONPATH = $oldPythonPath
}
