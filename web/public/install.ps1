# Genesis installer — Windows (PowerShell).
#
# Pull-not-push (SOVEREIGNTY.md): you ran this yourself; it sets up your AI on
# your own machine. The onboarding seed rides in the GENESIS_SEED env var the
# install command set — nothing is fetched from a server but the code itself.
#
# Usage (the web hands you this, with the seed filled in):
#   $env:GENESIS_SEED='<blob>'; irm https://<host>/install.ps1 | iex
$ErrorActionPreference = "Stop"

$Repo   = if ($env:GENESIS_REPO)     { $env:GENESIS_REPO }     else { "https://github.com/Ardaosta/Persistent_AI_Persona_Genesis" }
$AppDir = if ($env:GENESIS_APP_DIR)  { $env:GENESIS_APP_DIR }  else { Join-Path $HOME ".genesis-app" }

function Have($name) { $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

# Real Python vs the Microsoft Store alias: a fresh Win11 has `python` and
# `python3` as Store stubs on PATH that open the Store instead of running. They
# live under WindowsApps and report no real version. Prefer the `py` launcher
# (only present with a real install); otherwise accept `python` ONLY if it isn't
# the stub and actually prints a version.
function Find-Python {
  if (Have "py") { return "py" }
  $g = Get-Command "python" -ErrorAction SilentlyContinue
  if ($g -and ($g.Source -notlike "*WindowsApps*")) {
    $v = & python --version 2>$null
    if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") { return "python" }
  }
  return $null
}

Write-Host "Genesis: setting up your AI's home..."

# 1. prerequisites — both are human-installable; explain rather than guess.
$Py = Find-Python
if (-not $Py) {
  Write-Host "Python 3 is required. Install it from https://www.python.org/downloads/"
  Write-Host "  (on the first installer screen, check 'Add python.exe to PATH'), then run this again."
  Write-Host "  Or, if you have winget:  winget install -e --id Python.Python.3.12"
  exit 1
}
if (-not (Have "git")) {
  Write-Host "git is required. Install it from https://git-scm.com/download/win and run this again."
  exit 1
}

# 2. fetch the code (shallow; update in place if already there)
# Genesis is a PUBLIC repo, so no credentials are needed. Disable the credential
# helper + terminal prompt so Git for Windows' credential manager doesn't try to
# prompt on a headless/no-tty run (it fails with "could not read Username").
$env:GIT_TERMINAL_PROMPT = "0"
$NoCred = @("-c", "credential.helper=", "-c", "credential.interactive=false")
if (Test-Path (Join-Path $AppDir ".git")) {
  Write-Host "Updating Genesis in $AppDir"
  git @NoCred -C $AppDir pull --ff-only
} else {
  Write-Host "Downloading Genesis into $AppDir"
  git @NoCred clone --depth 1 $Repo $AppDir
}
if ($LASTEXITCODE -ne 0) {
  Write-Host "Could not download Genesis from $Repo. Check your internet connection and try again."
  exit 1
}

# 3. install into a private venv
Write-Host "Installing..."
& $Py -m venv (Join-Path $AppDir ".venv")
$VPy = Join-Path $AppDir ".venv\Scripts\python.exe"
& $VPy -m pip install -q --upgrade pip
& $VPy -m pip install -q `
  -e (Join-Path $AppDir "packages\genesis-memory") `
  -e (Join-Path $AppDir "packages\genesis-backend") `
  -e (Join-Path $AppDir "packages\genesis-core")

# 4. stand up the tuned home. The seed (GENESIS_SEED) is read by init itself; for
# the Claude-subscription path it also wires Claude Code (Mode B) here.
Write-Host "Standing up your AI's home (tuned to your setup answers)..."
& $VPy -m genesis_core.cli init

$Genesis = Join-Path $AppDir ".venv\Scripts\genesis.exe"
$Mode = (& $VPy -m genesis_core.cli seed-mode).Trim()

if ($Mode -eq "claude-code") {
  # Mode B: Claude is the brain. init already wired CLAUDE.md + the boot hook and
  # printed how to open it in the Claude desktop app. Nothing to launch here.
  Write-Host ""
  Write-Host "All set. Follow the steps above to open your AI in the Claude app's 'Code' tab."
} else {
  # Mode A: a double-click "Talk to your AI" launcher, then flow straight into
  # connecting a brain + the first conversation (the agent guides the key step).
  try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $launcher = Join-Path $desktop "Talk to your AI.bat"
    @"
@echo off
title Your AI
"$Genesis" install
"@ | Set-Content -Path $launcher -Encoding ASCII
  } catch { }
  Write-Host ""
  Write-Host "Your AI's home is ready. Let's wake it up..."
  Write-Host ""
  & $VPy -m genesis_core.cli install
  Write-Host ""
  Write-Host "All set. From now on, just double-click 'Talk to your AI' on your Desktop."
}
