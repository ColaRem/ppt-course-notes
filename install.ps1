# Install the ppt-course-notes skill into the DSH user skills root.
# Usage: powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"

$workspace = $PSScriptRoot
$source = Join-Path $workspace ".dsh\skills\ppt-course-notes"
if (-not (Test-Path -LiteralPath $source)) {
    throw "Skill source not found: $source"
}

$dshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE ".dsh" }
$target = Join-Path $dshHome "skills\ppt-course-notes"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
Copy-Item -LiteralPath $source -Destination $target -Recurse -Force

Write-Host "Installed: $target"
Write-Host "Open a new session (or refresh the skill catalog) to use ppt-course-notes."