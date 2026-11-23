<#
.SYNOPSIS
    Converts a local screen/Playwright walkthrough video into docs/assets/demo-60s.gif
    (1280x720, 15fps, palettegen/paletteuse, <= 8 MB) for the GitHub README.

.EXAMPLE
    .\scripts\record_demo_gif.ps1 -InputVideo .\demo-raw.mp4
#>
param(
    [Parameter(Mandatory = $false)]
    [string]$InputVideo = "docs/assets/demo-raw.mp4",

    [Parameter(Mandatory = $false)]
    [string]$OutputGif = "docs/assets/demo-60s.gif",

    [Parameter(Mandatory = $false)]
    [int]$Fps = 15,

    [Parameter(Mandatory = $false)]
    [int]$Width = 1280,

    [Parameter(Mandatory = $false)]
    [int]$MaxDurationSeconds = 60
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Error "ffmpeg is required on PATH to generate demo-60s.gif."
}

if (-not (Test-Path $InputVideo)) {
    Write-Error "Input video '$InputVideo' not found. Record a 45-60s walkthrough of http://localhost:3000 first."
}

$outDir = Split-Path -Parent $OutputGif
if ($outDir -and -not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}

$paletteFile = Join-Path $env:TEMP "rag_ops_palette.png"
$filterComplex = "fps=$Fps,scale=${Width}:-1:flags=lanczos"

Write-Host "Generating 2-pass palette from $InputVideo ..."
ffmpeg -y -t $MaxDurationSeconds -i $InputVideo -vf "$filterComplex,palettegen=stats_mode=diff" $paletteFile

Write-Host "Encoding $OutputGif ..."
ffmpeg -y -t $MaxDurationSeconds -i $InputVideo -i $paletteFile `
    -lavfi "$filterComplex [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" `
    $OutputGif

Remove-Item -Force -ErrorAction SilentlyContinue $paletteFile

$sizeMb = [math]::Round((Get-Item $OutputGif).Length / 1MB, 2)
Write-Host "Created $OutputGif ($sizeMb MB)"
if ($sizeMb -gt 8.0) {
    Write-Warning "GIF exceeds 8 MB ($sizeMb MB). Re-run with -Fps 12 or -Width 1024 to shrink."
}
