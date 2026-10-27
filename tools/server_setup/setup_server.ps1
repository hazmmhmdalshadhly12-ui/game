# setup_server.ps1 — TLS asset pipeline on Windows Server
# Run as Administrator on the AWS EC2 Windows instance (18.215.242.76).
# Installs portable Blender 5.0.1 + Git, clones the repo, runs the AAA sculpt
# pipeline headless, and pushes results to the feature branch.
#
# NOTE: requires outbound internet + the repo credentials supplied interactively
# (never hardcode tokens here).

$ErrorActionPreference = "Stop"
$Root = "C:\TLS"
New-Item -ItemType Directory -Force -Path "$Root\tools" | Out-Null
Set-Location $Root

Write-Host "== 1/5 Blender 5.0.1 portable =="
if (-not (Test-Path "$Root\tools\blender")) {
    Invoke-WebRequest -Uri "https://download.blender.org/release/Blender5.0/blender-5.0.1-windows-x64.zip" `
        -OutFile "$Root\tools\blender.zip"
    Expand-Archive "$Root\tools\blender.zip" -DestinationPath "$Root\tools"
    Rename-Item "$Root\tools\blender-5.0.1-windows-x64" "$Root\tools\blender"
}
$env:Path += ";$Root\tools\blender"

Write-Host "== 2/5 Git for Windows =="
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Invoke-WebRequest -Uri "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe" `
        -OutFile "$Root\tools\gitsetup.exe"
    Start-Process "$Root\tools\gitsetup.exe" -ArgumentList "/VERYSILENT /NORESTART" -Wait
}

Write-Host "== 3/5 Clone repo =="
if (-not (Test-Path "$Root\game")) {
    git clone https://github.com/hazmmhmdalshadhly12-ui/game "$Root\game"
}
Set-Location "$Root\game"
git fetch origin
git checkout -B feature/aaa-digital-sculpting-assets origin/main

Write-Host "== 4/5 Run AAA pipeline (headless) =="
$BL = "$Root\tools\blender\blender.exe"
& $BL --background --factory-startup --python "02_Art/aaa_pipeline/build_edmund_v2.py"
& $BL --background --factory-startup --python "02_Art/aaa_pipeline/build_npcs.py"
& $BL --background --factory-startup --python "02_Art/aaa_pipeline/build_env_v2.py"
& $BL --background --factory-startup --python "02_Art/aaa_pipeline/build_props_v2.py"
& $BL --background --factory-startup --python "02_Art/aaa_pipeline/verify_all_v2.py"

Write-Host "== 5/5 Commit + push =="
git add 02_Art
git commit -m "Server-run AAA sculpting pipeline results" --allow-empty
git push -u origin feature/aaa-digital-sculpting-assets

Write-Host "DONE. Review renders in 02_Art/renders/ and stats in 02_Art/exports/stats/."
