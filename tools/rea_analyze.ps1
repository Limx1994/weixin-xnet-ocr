# REA analysis wrapper (verified working)
#
# Purpose: run REA analysis on large PE files, bypassing the MCP session 2G heap cap.
# Verified: 2026-11-18, wxocr.dll (24MB) analyzed successfully in 313 seconds.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File E:\ocr\tools\rea_analyze.ps1 -Path <file>
#   powershell -ExecutionPolicy Bypass -File E:\ocr\tools\rea_analyze.ps1 -Path <file> -Out <json>
#   powershell -ExecutionPolicy Bypass -File E:\ocr\tools\rea_analyze.ps1 -Path <file> -NoDisableSwitch
#
# Keep this file ASCII-only: Windows PowerShell 5.1 reads BOM-less files as the
# active codepage (GBK here), which corrupts non-ASCII text.

param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$Out = '',

    [string]$Provider = 'ghidra',

    # Disables "Decompiler Switch Analysis", the slowest analyzer on large
    # statically linked DLLs (97.6s measured) and the trigger of JVM crashes.
    [switch]$NoDisableSwitch
)

$ErrorActionPreference = 'Stop'

# Core fix: the Ghidra analysis JVM defaults to -Xmx2G and its G1 concurrent GC
# thread dies with EXCEPTION_ACCESS_VIOLATION while importing large DLLs.
$env:GHIDRA_HEADLESS_MAXMEM = '8G'
if (-not $NoDisableSwitch) {
    $env:REA_GHIDRA_DISABLED_ANALYZERS = 'Decompiler Switch Analysis'
}

if (-not (Test-Path -LiteralPath $Path)) {
    throw "target not found: $Path"
}
if (-not [IO.Path]::IsPathRooted($Path)) {
    $Path = (Resolve-Path -LiteralPath $Path).Path
}

$node = 'C:\Users\90776\.local\bin\MCP\rea-main\dist\node\node.exe'
$rea  = 'C:\Users\90776\.local\bin\MCP\rea-main\dist\scripts\rea.mjs'
if (-not (Test-Path -LiteralPath $node)) { throw "REA node not found: $node" }
if (-not (Test-Path -LiteralPath $rea))  { throw "REA script not found: $rea" }

$reaArgs = @($rea, 'analyze', $Path, '--provider', $Provider, '--format', 'json')
if ($Out -ne '') {
    $reaArgs += @('--full-output')
}

Write-Host "Analyzing: $Path" -ForegroundColor Cyan
Write-Host ("Heap: {0}  Disabled analyzers: {1}" -f $env:GHIDRA_HEADLESS_MAXMEM, $env:REA_GHIDRA_DISABLED_ANALYZERS) -ForegroundColor DarkGray

$sw = [Diagnostics.Stopwatch]::StartNew()
$json = & $node @reaArgs 2>&1
$code = $LASTEXITCODE
$sw.Stop()

$text = $json -join "`n"
if ($Out -ne '') {
    [IO.File]::WriteAllText($Out, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Result written to: $Out" -ForegroundColor Green
}

Write-Host ("Elapsed: {0:N1}s  ExitCode: {1}" -f $sw.Elapsed.TotalSeconds, $code)

if ($code -ne 0) {
    Write-Host "Analysis failed. Tail of output:" -ForegroundColor Red
    $tail = $text.Substring([Math]::Max(0, $text.Length - 1500))
    Write-Host $tail
    exit $code
}

Write-Host "--- Summary ---" -ForegroundColor Green
try {
    $doc = $text | ConvertFrom-Json
    Write-Host ("EvidenceID: {0}" -f $doc.evidence_id)
    Write-Host ("Target:     {0}  ({1})" -f $doc.subject.name, $doc.subject.digest.sha256)
    $raw = $doc.raw_result
    if ($raw.segments)    { Write-Host ("Segments:   {0}" -f $raw.segments.Count) }
    if ($raw.procedures)  { Write-Host ("Procedures: {0}" -f $raw.procedures.Count) }
    if ($raw.strings)     { Write-Host ("Strings:    {0}" -f $raw.strings.Count) }
} catch {
    Write-Host "Summary not parsed; see the output file or the text above." -ForegroundColor Yellow
}

exit 0
