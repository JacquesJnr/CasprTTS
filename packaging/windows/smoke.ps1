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
        # A windowed bootloader reports startup errors in a modal dialog nobody can click in CI;
        # log every window (and child control) text of the stuck process before killing it.
        Add-Type -TypeDefinition @'
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text;
public static class SmokeWindows {
    delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int max);
    static string Text(IntPtr h) { var b = new StringBuilder(4096); GetWindowText(h, b, b.Capacity); return b.ToString(); }
    public static List<string> Dump(uint target) {
        var lines = new List<string>();
        EnumWindows((h, _) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid == target) {
                lines.Add("window: " + Text(h));
                EnumChildWindows(h, (c, __) => { var t = Text(c); if (t.Length > 0) lines.Add("  " + t); return true; }, IntPtr.Zero);
            }
            return true;
        }, IntPtr.Zero);
        return lines;
    }
}
'@
        $windows = [SmokeWindows]::Dump([uint32]$process.Id)
        $dump = "Stuck process windows:`n" + ($windows -join "`n")
        Write-Host $dump
        Set-Content -Path ($Report + '.windows.txt') -Value $dump -Encoding utf8
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
