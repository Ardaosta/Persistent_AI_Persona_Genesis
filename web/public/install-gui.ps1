# Genesis guided installer for Windows (a calm window, no terminal work).
#
# Pull-not-push (SOVEREIGNTY.md): the person ran this themselves, from a file
# they downloaded. It sets up their AI on their own computer. The onboarding
# seed rides in the GENESIS_SEED env var that the .bat set; nothing is fetched
# from any server but the code itself.
#
# How it is launched (the .bat the web hands out):
#   set "GENESIS_SEED=<blob>"
#   powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "irm <base>/install-gui.ps1 | iex"
#
# Shape: every step is a plain function that posts plain-language status into
# one shared table. The window is a thin shell over those functions (a worker
# runspace runs them, a timer paints the table). -NoGui runs the same functions
# in a row and prints each status line, so the logic can be tested without WPF.
#
# How to test on Windows (PowerShell 5.1, from a checkout):
#   # 1. parse check (must print 0)
#   $e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("$PWD\web\public\install-gui.ps1", [ref]$null, [ref]$e); $e.Count
#   # 2. the window builds (no Show); exit code 0
#   powershell -NoProfile -ExecutionPolicy Bypass -File web\public\install-gui.ps1 -XamlCheck; $LASTEXITCODE
#   # 3. the steps, no window, into a scratch folder, with a seed
#   $env:GENESIS_APP_DIR = "$env:TEMP\genesis-test"
#   $env:GENESIS_SEED    = "<blob from the web>"      # optional; init runs the local interview-free path without it
#   powershell -NoProfile -ExecutionPolicy Bypass -File web\public\install-gui.ps1 -NoGui -SkipClaudeCheck
#   # 4. the real thing (window), same env
#   powershell -NoProfile -ExecutionPolicy Bypass -File web\public\install-gui.ps1
#   # the log is at %LOCALAPPDATA%\Genesis\install.log
#
# Optional env: GENESIS_APP_DIR (where the code lives; default ~\.genesis-app),
# GENESIS_REPO (where to fetch it from).
[CmdletBinding()]
param(
  [switch]$NoGui,
  [switch]$SkipClaudeCheck,
  [switch]$XamlCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Off

# ---------------------------------------------------------------------------
# Shared state. One synchronized table; the worker writes, the window reads.
# ---------------------------------------------------------------------------
$script:S = [hashtable]::Synchronized(@{})
$S = $script:S
$S.IsWin        = ($env:OS -eq "Windows_NT")
$S.NoGui        = [bool]$NoGui
$S.SkipClaude   = [bool]$SkipClaudeCheck
$S.Repo         = if ($env:GENESIS_REPO)    { $env:GENESIS_REPO }    else { "https://github.com/Ardaosta/Persistent_AI_Persona_Genesis" }
$S.AppDir       = if ($env:GENESIS_APP_DIR) { $env:GENESIS_APP_DIR } else { Join-Path $HOME ".genesis-app" }
$S.HomeDir      = Join-Path $HOME "My AI"
$S.Name         = "your AI"
$S.Python       = $null      # full path to a real python.exe once found
$S.Git          = "git"
$S.Mode         = "agent"
$S.ClaudeLaunch = $null      # how to open the Claude app, once found
$S.HasWinget    = $false
$S.Step         = 0          # 1-based index of the step in progress
$S.StepState    = [hashtable]::Synchronized(@{})   # index -> pending|working|done|soft
$S.Message      = "Getting started."
$S.Phase        = "working"  # working | waiting | error | done
$S.Button       = ""         # button label while waiting or after an error
$S.Continue     = $false     # the window sets this when the person clicks continue
$S.Failed       = $false
$S.Log          = New-Object System.Collections.ArrayList
$S.Steps = @(
  "Checking this computer",
  "Getting Python ready",
  "Getting Git ready",
  "Downloading your AI",
  "Setting things up",
  "Making its home",
  "Checking for the Claude app"
)
for ($i = 1; $i -le $S.Steps.Count; $i++) { $S.StepState[$i] = "pending" }

# Log file: %LOCALAPPDATA%\Genesis\install.log (a temp folder elsewhere).
$logRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Genesis" } else { Join-Path ([System.IO.Path]::GetTempPath()) "Genesis" }
try { if (-not (Test-Path $logRoot)) { New-Item -ItemType Directory -Path $logRoot -Force | Out-Null } } catch { }
$S.LogPath = Join-Path $logRoot "install.log"

# ---------------------------------------------------------------------------
# Small helpers (shared by the window and -NoGui).
# ---------------------------------------------------------------------------
function Write-Log {
  param([string]$Text)
  $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
  [void]$S.Log.Add($line)
  try { Add-Content -Path $S.LogPath -Value $line -Encoding UTF8 } catch { }
}

function Get-LogText {
  return (($S.Log | ForEach-Object { "$_" }) -join [Environment]::NewLine)
}

function Set-Status {
  param([string]$Text)
  $S.Message = $Text
  Write-Log ("status: " + $Text)
  if ($S.NoGui) { Write-Host $Text }
}

function Start-Step {
  param([int]$Index, [string]$Text)
  $S.Step = $Index
  $S.StepState[$Index] = "working"
  Write-Log ("---- step {0}: {1}" -f $Index, $S.Steps[$Index - 1])
  if ($Text) { Set-Status $Text }
}

function Complete-Step {
  param([int]$Index)
  $S.StepState[$Index] = "done"
}

function Have {
  param([string]$Name)
  return ($null -ne (Get-Command $Name -ErrorAction SilentlyContinue))
}

# Run a program without a window, capture everything it says, log it all.
# Returns @{ Code = <exit code>; Output = <stdout+stderr text> }.
function Invoke-Native {
  param(
    [string]$Exe,
    [string[]]$Arguments = @(),
    [hashtable]$Env = @{},
    [string]$WorkDir = $null
  )
  $quoted = foreach ($a in $Arguments) {
    if ($a -eq "" -or $a -match '[\s"]') { '"' + ($a -replace '"', '\"') + '"' } else { $a }
  }
  $cmdline = "$Exe " + ($quoted -join " ")
  Write-Log ("run: " + $cmdline)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $Exe
  $psi.Arguments = ($quoted -join " ")
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  if ($WorkDir) { $psi.WorkingDirectory = $WorkDir }
  foreach ($k in $Env.Keys) { $psi.EnvironmentVariables[$k] = [string]$Env[$k] }
  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi
  try {
    [void]$p.Start()
  } catch {
    Write-Log ("  could not start: " + $_.Exception.Message)
    return @{ Code = 9009; Output = $_.Exception.Message }
  }
  $outTask = $p.StandardOutput.ReadToEndAsync()
  $errTask = $p.StandardError.ReadToEndAsync()
  $p.WaitForExit()
  $out = ($outTask.Result + $errTask.Result).Trim()
  if ($out) { foreach ($l in ($out -split "`r?`n")) { Write-Log ("  | " + $l) } }
  Write-Log ("  exit " + $p.ExitCode)
  return @{ Code = $p.ExitCode; Output = $out }
}

# Re-read PATH from the registry (HKLM then HKCU) so a program winget just
# installed is visible to this same process without a restart.
function Update-PathFromRegistry {
  if (-not $S.IsWin) { return }
  $parts = New-Object System.Collections.ArrayList
  try {
    $m = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" -Name Path -ErrorAction SilentlyContinue).Path
    if ($m) { [void]$parts.Add([Environment]::ExpandEnvironmentVariables($m)) }
  } catch { }
  try {
    $u = (Get-ItemProperty "HKCU:\Environment" -Name Path -ErrorAction SilentlyContinue).Path
    if ($u) { [void]$parts.Add([Environment]::ExpandEnvironmentVariables($u)) }
  } catch { }
  if ($parts.Count -eq 0) {
    try {
      [void]$parts.Add([Environment]::GetEnvironmentVariable("Path", "Machine"))
      [void]$parts.Add([Environment]::GetEnvironmentVariable("Path", "User"))
    } catch { }
  }
  if ($parts.Count -gt 0) {
    $fresh = ($parts -join ";")
    # keep anything only this process knew about (venv bins etc.) at the end
    $env:Path = $fresh + ";" + $env:Path
    Write-Log "PATH refreshed from the registry."
  }
}

function Open-Url {
  param([string]$Url)
  Write-Log ("open: " + $Url)
  try { Start-Process $Url | Out-Null } catch { Write-Log ("  could not open the browser: " + $_.Exception.Message) }
}

# Pause until the person clicks the continue button (window mode). In -NoGui
# there is nobody to click, so this returns $false and the caller explains.
function Wait-ForPerson {
  param([string]$ButtonText, [string]$Text)
  if ($S.NoGui) {
    Set-Status ($Text + " Then run this again.")
    return $false
  }
  $S.Continue = $false
  $S.Button = $ButtonText
  $S.Phase = "waiting"
  Set-Status $Text
  while (-not $S.Continue) { Start-Sleep -Milliseconds 300 }
  $S.Continue = $false
  $S.Phase = "working"
  $S.Button = ""
  return $true
}

# The seed is base64url JSON; pull out the AI's name if it carries one.
function Get-SeedName {
  $blob = $env:GENESIS_SEED
  if (-not $blob) { return $null }
  try {
    $b = $blob.Trim().Replace("-", "+").Replace("_", "/")
    $pad = (4 - ($b.Length % 4)) % 4
    $b = $b + ("=" * $pad)
    $json = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b))
    $obj = $json | ConvertFrom-Json
    $n = "$($obj.name)".Trim()
    if ($n.Length -gt 0 -and $n.Length -le 60) { return $n }
  } catch { }
  return $null
}

# ---------------------------------------------------------------------------
# Finding things.
# ---------------------------------------------------------------------------

# Ask a candidate python for its version and real path. Returns the path of a
# 3.9+ interpreter, or $null.
function Test-PythonCandidate {
  param([string]$Exe, [string[]]$Prefix = @())
  $r = Invoke-Native $Exe ($Prefix + @("-c", "import sys;print('%d.%d' % sys.version_info[:2]);print(sys.executable)"))
  if ($r.Code -ne 0) { return $null }
  $lines = @($r.Output -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
  if ($lines.Count -lt 2) { return $null }
  $v = $lines[0].Trim(); $path = $lines[-1].Trim()
  $ok = $false
  try { $ok = ([version]$v) -ge ([version]"3.9") } catch { }
  if (-not $ok) { Write-Log ("  python at $path is $v, too old"); return $null }
  if ($path -like "*WindowsApps*") { Write-Log "  that is the Store stub, skipping"; return $null }
  return $path
}

# Real Python vs the Microsoft Store alias: a fresh Windows has `python` and
# `python3` stubs on PATH (under WindowsApps) that open the Store instead of
# running. Prefer the `py` launcher (only a real install has it); accept
# `python` only if it is not the stub and really answers. Then look in the
# usual per-user install folder in case PATH has not caught up yet.
function Find-Python {
  if (Have "py") {
    $p = Test-PythonCandidate "py" @("-3")
    if ($p) { return $p }
  }
  foreach ($name in @("python", "python3")) {
    $g = Get-Command $name -ErrorAction SilentlyContinue
    if ($g -and ($g.Source -notlike "*WindowsApps*")) {
      $p = Test-PythonCandidate $g.Source
      if ($p) { return $p }
    }
  }
  if ($S.IsWin) {
    $roots = @()
    if ($env:LOCALAPPDATA) { $roots += (Join-Path $env:LOCALAPPDATA "Programs\Python") }
    if ($env:ProgramFiles) { $roots += $env:ProgramFiles }
    foreach ($root in $roots) {
      if (-not (Test-Path $root)) { continue }
      $dirs = Get-ChildItem -Path $root -Directory -Filter "Python3*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
      foreach ($d in $dirs) {
        $exe = Join-Path $d.FullName "python.exe"
        if (Test-Path $exe) {
          $p = Test-PythonCandidate $exe
          if ($p) { return $p }
        }
      }
    }
  }
  return $null
}

function Find-Git {
  $g = Get-Command "git" -ErrorAction SilentlyContinue
  if ($g) { return $g.Source }
  if ($S.IsWin) {
    $cands = @()
    if ($env:ProgramFiles)      { $cands += (Join-Path $env:ProgramFiles "Git\cmd\git.exe") }
    if (${env:ProgramFiles(x86)}) { $cands += (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe") }
    if ($env:LOCALAPPDATA)      { $cands += (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe") }
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
  }
  return $null
}

# The Claude desktop app on Windows. Verified 2026-09-21 against claude.com/download
# (the Windows download is an MSIX package; the enterprise page at
# support.claude.com/en/articles/12622703 installs it per user with
# Add-AppxPackage) plus the Claude Code issue tracker for the older Squirrel
# layout. So, in order:
#   1. an installed Appx/MSIX package named Claude* (family Claude_pzs8sxrjxfjjc);
#      launched through the Start Apps folder so we never need its hidden path
#   2. the WindowsApps alias %LOCALAPPDATA%\Microsoft\WindowsApps\Claude.exe
#   3. the older per-user layout %LOCALAPPDATA%\AnthropicClaude\claude.exe
#      (and app-*\claude.exe under it)
#   4. the Start Menu shortcut (per user, then all users)
#   5. the Uninstall registry keys (HKCU, HKLM, HKLM WOW6432Node)
# Returns something Start-Process can open, or $null.
function Find-ClaudeApp {
  if (-not $S.IsWin) { return $null }
  try {
    if (Have "Get-StartApps") {
      $apps = @(Get-StartApps -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq "Claude" -or $_.AppID -like "Claude_*!*" })
      if ($apps.Count -gt 0) { Write-Log ("claude: start app " + $apps[0].AppID); return ("shell:AppsFolder\" + $apps[0].AppID) }
    }
  } catch { Write-Log ("claude: Get-StartApps failed: " + $_.Exception.Message) }
  try {
    if (Have "Get-AppxPackage") {
      $pkg = @(Get-AppxPackage -Name "Claude*" -ErrorAction SilentlyContinue)
      if ($pkg.Count -gt 0) {
        Write-Log ("claude: appx package " + $pkg[0].PackageFullName)
        $alias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\Claude.exe"
        if (Test-Path $alias) { return $alias }
        return ("shell:AppsFolder\" + $pkg[0].PackageFamilyName + "!Claude")
      }
    }
  } catch { Write-Log ("claude: Get-AppxPackage failed: " + $_.Exception.Message) }
  if ($env:LOCALAPPDATA) {
    $alias = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\Claude.exe"
    if (Test-Path $alias) { Write-Log "claude: WindowsApps alias"; return $alias }
    $legacy = Join-Path $env:LOCALAPPDATA "AnthropicClaude"
    if (Test-Path $legacy) {
      $stub = Join-Path $legacy "claude.exe"
      if (Test-Path $stub) { Write-Log "claude: legacy stub"; return $stub }
      $vers = Get-ChildItem -Path $legacy -Directory -Filter "app-*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
      foreach ($v in $vers) {
        $exe = Join-Path $v.FullName "claude.exe"
        if (Test-Path $exe) { Write-Log ("claude: legacy " + $exe); return $exe }
      }
    }
  }
  $menus = @()
  if ($env:APPDATA)     { $menus += (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs") }
  if ($env:ProgramData) { $menus += (Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs") }
  foreach ($m in $menus) {
    foreach ($lnk in @("Claude.lnk", "Anthropic\Claude.lnk")) {
      $p = Join-Path $m $lnk
      if (Test-Path $p) { Write-Log ("claude: shortcut " + $p); return $p }
    }
  }
  $keys = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
  )
  foreach ($k in $keys) {
    try {
      $hits = @(Get-ItemProperty $k -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "Claude*" -and ($_.Publisher -like "*Anthropic*" -or $_.DisplayName -eq "Claude") })
      foreach ($h in $hits) {
        $icon = "$($h.DisplayIcon)" -replace ',\d+$', ''
        $icon = $icon.Trim('"')
        if ($icon -and (Test-Path $icon)) { Write-Log ("claude: uninstall key icon " + $icon); return $icon }
        if ($h.InstallLocation) {
          $exe = Join-Path "$($h.InstallLocation)" "claude.exe"
          if (Test-Path $exe) { Write-Log ("claude: uninstall key location " + $exe); return $exe }
        }
      }
    } catch { }
  }
  return $null
}

# ---------------------------------------------------------------------------
# The steps. Each throws a plain sentence on failure; nothing technical.
# ---------------------------------------------------------------------------
function Step-CheckComputer {
  Start-Step 1 "Taking a quick look at this computer."
  $os = [Environment]::OSVersion
  Write-Log ("os: " + $os.VersionString + "  64-bit: " + [Environment]::Is64BitOperatingSystem)
  Write-Log ("powershell: " + $PSVersionTable.PSVersion + "  app dir: " + $S.AppDir)
  if ($S.IsWin) {
    if ($os.Version.Major -lt 10) {
      throw "This computer's Windows is older than this setup can use. Please tell the person who sent you this."
    }
  } else {
    Write-Log "not Windows: the Windows-only parts will not work here (test mode)."
    Set-Status "This is not a Windows computer, so some steps will not work here."
  }
  $S.HasWinget = Have "winget"
  Write-Log ("winget: " + $S.HasWinget)
  Complete-Step 1
}

function Step-EnsurePython {
  Start-Step 2 "Checking whether Python is already here."
  $py = Find-Python
  if (-not $py -and $S.HasWinget) {
    Set-Status "Installing Python. This can take a few minutes."
    $r = Invoke-Native "winget" @("install", "-e", "--id", "Python.Python.3.12", "--scope", "user", "--silent",
                                  "--accept-package-agreements", "--accept-source-agreements")
    Update-PathFromRegistry
    $py = Find-Python
    if (-not $py) { Write-Log ("winget python exit " + $r.Code + ", still not found") }
  }
  $tries = 0
  while (-not $py) {
    $tries++
    if ($tries -gt 5) { throw "Python still could not be found after installing. Please tell the person who sent you this and send them the details." }
    Open-Url "https://www.python.org/downloads/"
    $ok = Wait-ForPerson "I've installed Python, continue" "Python is needed and could not be installed automatically. A web page has opened: click the big yellow Download button there, run it, and tick 'Add python.exe to PATH' on its first screen. When it finishes, come back here."
    if (-not $ok) { throw "Python is not installed on this computer, and it could not be installed automatically. Please install it from python.org and run this again, or tell the person who sent you this." }
    Set-Status "Looking for Python again."
    Update-PathFromRegistry
    $py = Find-Python
  }
  $S.Python = $py
  Write-Log ("python: " + $py)
  Complete-Step 2
}

function Step-EnsureGit {
  Start-Step 3 "Checking whether Git is already here."
  $git = Find-Git
  $installed = $false
  if (-not $git -and $S.HasWinget) {
    Set-Status "Installing Git. This can take a minute or two."
    $r = Invoke-Native "winget" @("install", "-e", "--id", "Git.Git", "--silent",
                                  "--accept-package-agreements", "--accept-source-agreements")
    Update-PathFromRegistry
    $git = Find-Git
    if ($git) { $installed = $true } else { Write-Log ("winget git exit " + $r.Code + ", still not found") }
  }
  $tries = 0
  while (-not $git) {
    $tries++
    if ($tries -gt 5) { throw "Git still could not be found after installing. Please tell the person who sent you this and send them the details." }
    Open-Url "https://git-scm.com/download/win"
    $ok = Wait-ForPerson "I've installed Git, continue" "Git is needed and could not be installed automatically. A web page has opened: choose the 64-bit installer there, run it, and click Next on every screen. When it finishes, come back here."
    if (-not $ok) { throw "Git is not installed on this computer, and it could not be installed automatically. Please install it from git-scm.com and run this again, or tell the person who sent you this." }
    Set-Status "Looking for Git again."
    Update-PathFromRegistry
    $git = Find-Git
    if ($git) { $installed = $true }
  }
  $S.Git = $git
  Write-Log ("git: " + $git)
  # A silent Git install picks Vim as its editor. Nobody should ever land in Vim.
  if ($installed) {
    [void](Invoke-Native $git @("config", "--global", "core.editor", "notepad"))
  }
  Complete-Step 3
}

function Step-Download {
  Start-Step 4 ("Downloading " + $S.Name + ". This needs the internet and usually takes under a minute.")
  # Public repo, so no login. Turn off the credential helper and any prompt so
  # nothing can pop up asking for a username on a windowless run.
  $gitEnv = @{ GIT_TERMINAL_PROMPT = "0" }
  $noCred = @("-c", "credential.helper=", "-c", "credential.interactive=false")
  $appDir = $S.AppDir
  if (Test-Path (Join-Path $appDir ".git")) {
    $r = Invoke-Native $S.Git ($noCred + @("-C", $appDir, "pull", "--ff-only")) $gitEnv
    if ($r.Code -ne 0) {
      # keep what is there, like install.sh does; the later steps still work
      Write-Log "pull failed; keeping the copy already here."
      Set-Status "Could not fetch the newest version; using the copy already here."
    }
  } else {
    $parent = Split-Path -Parent $appDir
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    $r = Invoke-Native $S.Git ($noCred + @("clone", "--depth", "1", $S.Repo, $appDir)) $gitEnv
    if ($r.Code -ne 0) {
      throw "The download did not finish. Check that this computer is connected to the internet, then run this again. If it keeps happening, tell the person who sent you this."
    }
  }
  Complete-Step 4
}

function Step-Setup {
  Start-Step 5 "Setting things up. This is the slow part, usually two to five minutes. Nothing needs you right now."
  $venv = Join-Path $S.AppDir ".venv"
  $vpy  = Join-Path $venv "Scripts\python.exe"
  if (-not (Test-Path $vpy)) {
    $r = Invoke-Native $S.Python @("-m", "venv", $venv)
    if ($r.Code -ne 0 -or -not (Test-Path $vpy)) {
      throw "Python could not set up its private workspace. Please tell the person who sent you this and send them the details."
    }
  }
  $S.VenvPython = $vpy
  [void](Invoke-Native $vpy @("-m", "pip", "install", "-q", "--upgrade", "pip"))
  $pkgs = @("genesis-memory", "genesis-backend", "genesis-core")
  $pipArgs = @("-m", "pip", "install", "-q")
  foreach ($p in $pkgs) { $pipArgs += @("-e", (Join-Path $S.AppDir ("packages\" + $p))) }
  $r = Invoke-Native $vpy $pipArgs
  if ($r.Code -ne 0) {
    throw "One of the pieces did not install. This is usually the internet dropping for a moment; run this again. If it keeps happening, tell the person who sent you this and send them the details."
  }
  Complete-Step 5
}

function Step-MakeHome {
  Start-Step 6 ("Making a home for " + $S.Name + ".")
  $env:PYTHONIOENCODING = "utf-8"
  $r = Invoke-Native $S.VenvPython @("-m", "genesis_core.cli", "init")
  if ($r.Code -ne 0) {
    throw ("Setting up " + $S.Name + "'s home did not finish. Please tell the person who sent you this and send them the details.")
  }
  $m = Invoke-Native $S.VenvPython @("-m", "genesis_core.cli", "seed-mode")
  $mode = "agent"
  if ($m.Code -eq 0 -and $m.Output) {
    $last = @($m.Output -split "`r?`n" | Where-Object { $_.Trim() -ne "" })[-1]
    if ($last) { $mode = $last.Trim() }
  }
  $S.Mode = $mode
  Write-Log ("mode: " + $mode)
  if ($mode -ne "claude-code" -and $mode -ne "codex") {
    # Mode A gets a double-click launcher on the Desktop, like install.ps1.
    try {
      $exe = Join-Path $S.AppDir ".venv\Scripts\genesis.exe"
      $desktop = [Environment]::GetFolderPath("Desktop")
      if ($desktop -and (Test-Path $desktop)) {
        $launcher = Join-Path $desktop "Talk to your AI.bat"
        ("@echo off`r`ntitle Your AI`r`n`"" + $exe + "`" install`r`n") | Set-Content -Path $launcher -Encoding ASCII
        Write-Log ("launcher: " + $launcher)
      }
    } catch { Write-Log ("launcher not written: " + $_.Exception.Message) }
  }
  Complete-Step 6
}

function Step-CheckClaude {
  Start-Step 7 "Looking for the Claude app."
  if ($S.SkipClaude) {
    Write-Log "claude check skipped by switch."
    Complete-Step 7
    return
  }
  if ($S.Mode -ne "claude-code") {
    Write-Log ("claude check not needed for mode " + $S.Mode)
    Complete-Step 7
    return
  }
  $app = Find-ClaudeApp
  $tries = 0
  while (-not $app) {
    $tries++
    if ($tries -gt 5) { break }
    Open-Url "https://claude.ai/download"
    $ok = Wait-ForPerson "I've installed Claude, continue" "The Claude app is not on this computer yet. A web page has opened: choose the Windows download there and run it. Once it opens and you have signed in, come back here."
    if (-not $ok) { break }
    Set-Status "Looking for the Claude app again."
    $app = Find-ClaudeApp
  }
  $S.ClaudeLaunch = $app
  if (-not $app) {
    Write-Log "claude app not found; the done screen will offer the download page."
    $S.StepState[7] = "soft"
  } else {
    Write-Log ("claude: " + $app)
    Complete-Step 7
  }
}

# Run everything, in order, turning any failure into one calm sentence.
function Invoke-AllSteps {
  try {
    Write-Log "==== Genesis guided install starting"
    $n = Get-SeedName
    if ($n) { $S.Name = $n }
    Write-Log ("name: " + $S.Name + "  seed present: " + [bool]$env:GENESIS_SEED)
    Step-CheckComputer
    Step-EnsurePython
    Step-EnsureGit
    Step-Download
    Step-Setup
    Step-MakeHome
    Step-CheckClaude
    $S.Phase = "done"
    if ($S.Mode -eq "claude-code") {
      Set-Status ($S.Name + " is ready to meet you.")
    } elseif ($S.Mode -eq "codex") {
      Set-Status ($S.Name + " is ready. Open Codex and choose the folder " + $S.HomeDir + ".")
    } else {
      Set-Status ($S.Name + " is ready. Time for a first hello.")
    }
    Write-Log "==== done"
  } catch {
    $S.Failed = $true
    $S.Phase = "error"
    $S.Button = "Copy details"
    if ($S.Step -ge 1) { $S.StepState[$S.Step] = "soft" }
    $msg = "$($_.Exception.Message)"
    Write-Log ("FAILED at step " + $S.Step + ": " + $msg)
    if ($_.ScriptStackTrace) { Write-Log ("  at " + ($_.ScriptStackTrace -replace "`r?`n", " / ")) }
    # Sentences we wrote are already plain; anything else gets a gentle wrapper.
    if ($msg -notmatch "tell the person who sent you this|run this again") {
      $msg = "Something did not go as planned. Please tell the person who sent you this, and send them the details (the button below copies them)."
    }
    Set-Status $msg
    if ($S.NoGui) { Write-Host ("Details are in " + $S.LogPath) }
  }
}

# ---------------------------------------------------------------------------
# Done-screen actions (also usable from -NoGui, mostly for completeness).
# ---------------------------------------------------------------------------
function Copy-ToClipboard {
  param([string]$Text)
  if (Have "Set-Clipboard") {
    try { Set-Clipboard -Value $Text; return $true } catch { Write-Log ("clipboard: " + $_.Exception.Message) }
  }
  return $false
}

function Open-ClaudeApp {
  if ($S.ClaudeLaunch) {
    try { Start-Process $S.ClaudeLaunch | Out-Null; return } catch { Write-Log ("open claude: " + $_.Exception.Message) }
  }
  Open-Url "https://claude.ai/download"
}

function Open-HomeFolder {
  try { if (-not (Test-Path $S.HomeDir)) { New-Item -ItemType Directory -Path $S.HomeDir -Force | Out-Null } } catch { }
  if ($S.IsWin) {
    try { Start-Process "explorer.exe" -ArgumentList ('"' + $S.HomeDir + '"') | Out-Null } catch { Write-Log ("explorer: " + $_.Exception.Message) }
  } else {
    Write-Host ("(folder: " + $S.HomeDir + ")")
  }
}

# Mode A: a visible console for the first conversation, like install.ps1.
function Start-TalkToYourAI {
  if (-not $S.IsWin) { Write-Host "(would open a console and run: genesis install)"; return }
  $cmd = "& '" + $S.VenvPython + "' -m genesis_core.cli install"
  try {
    Start-Process "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", $cmd) | Out-Null
  } catch { Write-Log ("talk: " + $_.Exception.Message) }
}

# ---------------------------------------------------------------------------
# The window.
# ---------------------------------------------------------------------------
$script:Xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Setting up your AI" Width="560" Height="640"
        ResizeMode="NoResize" WindowStartupLocation="CenterScreen"
        Background="#FAF8F4" FontFamily="Segoe UI" FontSize="15" Foreground="#2B2B2B">
  <Grid Margin="44,36,44,24">
    <Grid.RowDefinitions>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="*"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
      <RowDefinition Height="Auto"/>
    </Grid.RowDefinitions>

    <TextBlock x:Name="Heading" Grid.Row="0" FontSize="30" FontWeight="SemiBold" Foreground="#1F1F1F"
               TextWrapping="Wrap" Text="Setting up your AI"/>
    <TextBlock x:Name="Sub" Grid.Row="1" Margin="0,8,0,26" FontSize="15" Foreground="#6B6B6B" TextWrapping="Wrap"
               Text="This takes a few minutes and needs nothing from you. Feel free to make a cup of tea."/>

    <StackPanel x:Name="StepsPanel" Grid.Row="2" VerticalAlignment="Top">
      <StackPanel.Resources>
        <Style TargetType="Ellipse">
          <Setter Property="Width" Value="22"/>
          <Setter Property="Height" Value="22"/>
          <Setter Property="StrokeThickness" Value="1.5"/>
          <Setter Property="Stroke" Value="#CFC9BE"/>
          <Setter Property="Fill" Value="Transparent"/>
        </Style>
        <Style TargetType="TextBlock">
          <Setter Property="VerticalAlignment" Value="Center"/>
        </Style>
      </StackPanel.Resources>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot1"/><TextBlock x:Name="Mark1" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label1" Grid.Column="1" Text="Checking this computer"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot2"/><TextBlock x:Name="Mark2" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label2" Grid.Column="1" Text="Getting Python ready"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot3"/><TextBlock x:Name="Mark3" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label3" Grid.Column="1" Text="Getting Git ready"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot4"/><TextBlock x:Name="Mark4" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label4" Grid.Column="1" Text="Downloading your AI"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot5"/><TextBlock x:Name="Mark5" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label5" Grid.Column="1" Text="Setting things up"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot6"/><TextBlock x:Name="Mark6" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label6" Grid.Column="1" Text="Making its home"/></Grid>
      <Grid Margin="0,0,0,12"><Grid.ColumnDefinitions><ColumnDefinition Width="40"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Grid Grid.Column="0" Width="22" Height="22" HorizontalAlignment="Left"><Ellipse x:Name="Dot7"/><TextBlock x:Name="Mark7" FontSize="13" FontWeight="Bold" Foreground="White" HorizontalAlignment="Center" Text=""/></Grid>
        <TextBlock x:Name="Label7" Grid.Column="1" Text="Checking for the Claude app"/></Grid>
    </StackPanel>

    <StackPanel x:Name="DonePanel" Grid.Row="2" VerticalAlignment="Top" Visibility="Collapsed">
      <TextBlock x:Name="Done1" FontSize="16" TextWrapping="Wrap" Margin="0,0,0,14" Text=""/>
      <TextBlock x:Name="Done2" FontSize="16" TextWrapping="Wrap" Margin="0,0,0,14" Text=""/>
      <TextBlock x:Name="Done3" FontSize="16" TextWrapping="Wrap" Margin="0,0,0,14" Text=""/>
      <TextBlock x:Name="Done4" FontSize="14" Foreground="#6B6B6B" TextWrapping="Wrap" Margin="0,4,0,0" Text=""/>
    </StackPanel>

    <TextBlock x:Name="Status" Grid.Row="3" Margin="0,18,0,18" FontSize="15" Foreground="#3F3F3F" TextWrapping="Wrap"
               MinHeight="66" Text="Getting started."/>

    <StackPanel Grid.Row="4" Orientation="Horizontal" HorizontalAlignment="Left">
      <Button x:Name="Action" Content="Working..." IsEnabled="False" Padding="22,9" FontSize="15" Margin="0,0,12,0"
              Background="#6B8E6B" Foreground="White" BorderThickness="0" Cursor="Hand"/>
      <Button x:Name="Second" Content="Show me the folder" Visibility="Collapsed" Padding="22,9" FontSize="15"
              Background="#EAE6DE" Foreground="#2B2B2B" BorderThickness="0" Cursor="Hand"/>
    </StackPanel>

    <TextBlock Grid.Row="5" Margin="0,22,0,0" FontSize="12.5" Foreground="#9A958C" Text="Nothing about you leaves this computer."/>
  </Grid>
</Window>
'@

function New-InstallWindow {
  Add-Type -AssemblyName PresentationFramework
  Add-Type -AssemblyName PresentationCore
  Add-Type -AssemblyName WindowsBase
  $reader = New-Object System.Xml.XmlNodeReader ([xml]$script:Xaml)
  return [Windows.Markup.XamlReader]::Load($reader)
}

# Hide the console window if there is one (the .bat launches hidden anyway,
# but a double-clicked .ps1 or a visible console should still look calm).
function Hide-ConsoleWindow {
  if (-not $S.IsWin) { return }
  try {
    $sig = '[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow(); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);'
    $w = Add-Type -MemberDefinition $sig -Name "ConsoleHider" -Namespace "Genesis" -PassThru
    $h = $w::GetConsoleWindow()
    if ($h -ne [IntPtr]::Zero) { [void]$w::ShowWindow($h, 0) }
  } catch { }
}

function Start-Gui {
  Hide-ConsoleWindow
  $script:Window = New-InstallWindow
  $w = $script:Window
  $ui = @{}
  foreach ($n in @("Heading", "Sub", "StepsPanel", "DonePanel", "Done1", "Done2", "Done3", "Done4", "Status", "Action", "Second")) { $ui[$n] = $w.FindName($n) }
  for ($i = 1; $i -le 7; $i++) { $ui["Dot$i"] = $w.FindName("Dot$i"); $ui["Mark$i"] = $w.FindName("Mark$i"); $ui["Label$i"] = $w.FindName("Label$i") }
  $script:Ui = $ui

  $n = Get-SeedName
  if ($n) { $script:S.Name = $n }
  $ui.Heading.Text = "Setting up " + $script:S.Name
  $ui.Label4.Text = "Downloading " + $script:S.Name
  $w.Title = "Setting up " + $script:S.Name

  $accent = [Windows.Media.BrushConverter]::new().ConvertFromString("#6B8E6B")
  $soft   = [Windows.Media.BrushConverter]::new().ConvertFromString("#D9A441")
  $idle   = [Windows.Media.BrushConverter]::new().ConvertFromString("#CFC9BE")
  $clear  = [Windows.Media.Brushes]::Transparent
  $ink    = [Windows.Media.BrushConverter]::new().ConvertFromString("#2B2B2B")
  $dim    = [Windows.Media.BrushConverter]::new().ConvertFromString("#8A857C")
  $script:Brushes = @{ accent = $accent; soft = $soft; idle = $idle; clear = $clear; ink = $ink; dim = $dim }
  $script:DoneShown = $false

  # The worker: same functions, another thread. It sees $S and the functions.
  $iss = [System.Management.Automation.Runspaces.InitialSessionState]::CreateDefault()
  foreach ($fn in @("Write-Log", "Get-LogText", "Set-Status", "Start-Step", "Complete-Step", "Have", "Invoke-Native",
                    "Update-PathFromRegistry", "Open-Url", "Wait-ForPerson", "Get-SeedName", "Test-PythonCandidate",
                    "Find-Python", "Find-Git", "Find-ClaudeApp", "Step-CheckComputer", "Step-EnsurePython", "Step-EnsureGit",
                    "Step-Download", "Step-Setup", "Step-MakeHome", "Step-CheckClaude", "Invoke-AllSteps")) {
    $def = (Get-Command $fn -CommandType Function).Definition
    $iss.Commands.Add((New-Object System.Management.Automation.Runspaces.SessionStateFunctionEntry($fn, $def)))
  }
  $iss.Variables.Add((New-Object System.Management.Automation.Runspaces.SessionStateVariableEntry("S", $script:S, "shared state")))
  $rs = [RunspaceFactory]::CreateRunspace($iss)
  $rs.ApartmentState = "MTA"
  $rs.ThreadOptions = "ReuseThread"
  $rs.Open()
  $script:Worker = [PowerShell]::Create()
  $script:Worker.Runspace = $rs
  [void]$script:Worker.AddScript('$ErrorActionPreference = "Stop"; Invoke-AllSteps')
  $script:WorkerHandle = $script:Worker.BeginInvoke()

  $ui.Action.Add_Click({
    $st = $script:S
    switch ($st.Phase) {
      "waiting" { $script:Ui.Action.IsEnabled = $false; $script:Ui.Action.Content = "Working..."; $st.Continue = $true }
      "error"   { if (Copy-ToClipboard (Get-LogText)) { $script:Ui.Status.Text = "Copied. Paste the details into a message to the person who sent you this." } else { $script:Ui.Status.Text = "The details are in the file " + $st.LogPath } }
      "done"    { if ($st.Mode -eq "claude-code") { Open-ClaudeApp } elseif ($st.Mode -eq "codex") { Open-HomeFolder } else { Start-TalkToYourAI } }
    }
  })
  $ui.Second.Add_Click({ Open-HomeFolder })

  $timer = New-Object System.Windows.Threading.DispatcherTimer
  $timer.Interval = [TimeSpan]::FromMilliseconds(250)
  $timer.Add_Tick({
    $st = $script:S; $u = $script:Ui; $b = $script:Brushes
    for ($i = 1; $i -le 7; $i++) {
      $state = $st.StepState[$i]
      $dot = $u["Dot$i"]; $mark = $u["Mark$i"]; $label = $u["Label$i"]
      switch ($state) {
        "working" { $dot.Stroke = $b.accent; $dot.Fill = $b.clear; $mark.Text = ""; $label.FontWeight = [Windows.FontWeights]::SemiBold; $label.Foreground = $b.accent }
        "done"    { $dot.Stroke = $b.accent; $dot.Fill = $b.accent; $mark.Text = [string][char]0x2713; $label.FontWeight = [Windows.FontWeights]::Normal; $label.Foreground = $b.ink }
        "soft"    { $dot.Stroke = $b.soft; $dot.Fill = $b.soft; $mark.Text = "!"; $label.FontWeight = [Windows.FontWeights]::Normal; $label.Foreground = $b.ink }
        default   { $dot.Stroke = $b.idle; $dot.Fill = $b.clear; $mark.Text = ""; $label.FontWeight = [Windows.FontWeights]::Normal; $label.Foreground = $b.dim }
      }
    }
    if ($u.Status.Text -ne $st.Message -and -not ($st.Phase -eq "error" -and $u.Status.Text -like "Copied.*") -and -not ($st.Phase -eq "error" -and $u.Status.Text -like "The details are in*")) {
      $u.Status.Text = $st.Message
    }
    switch ($st.Phase) {
      "working" { $u.Action.Content = "Working..."; $u.Action.IsEnabled = $false }
      "waiting" { $u.Action.Content = $st.Button; $u.Action.IsEnabled = $true }
      "error"   { $u.Action.Content = "Copy details"; $u.Action.IsEnabled = $true; $u.Sub.Text = "Something needs a hand. Nothing is broken, and nothing about you has gone anywhere." }
      "done"    {
        if (-not $script:DoneShown) {
          $script:DoneShown = $true
          $u.StepsPanel.Visibility = "Collapsed"
          $u.DonePanel.Visibility = "Visible"
          $u.Second.Visibility = "Visible"
          $u.Action.IsEnabled = $true
          if ($st.Mode -eq "claude-code") {
            $u.Heading.Text = $st.Name + " is ready to meet you"
            $u.Sub.Text = "Three small things and you are talking."
            $u.Done1.Text = "1.  Open the Claude app and sign in if it asks."
            $u.Done2.Text = "2.  Click Code at the top of the Claude window."
            $u.Done3.Text = "3.  When it asks for a folder, paste into the folder box. The folder's address is already copied for you, so just press Ctrl+V and choose it."
            $u.Done4.Text = "The folder is " + $st.HomeDir
            $u.Action.Content = "Open Claude"
            [void](Copy-ToClipboard $st.HomeDir)
            if (-not $st.ClaudeLaunch) { $u.Done1.Text = "1.  Install the Claude app (the button below opens the download page), then open it and sign in." }
          } elseif ($st.Mode -eq "codex") {
            $u.Heading.Text = $st.Name + " is ready to meet you"
            $u.Sub.Text = "Two small things and you are talking."
            $u.Done1.Text = "1.  Open Codex."
            $u.Done2.Text = "2.  When it asks for a folder, paste into the folder box. The folder's address is already copied for you, so just press Ctrl+V and choose it."
            $u.Done3.Text = ""
            $u.Done4.Text = "The folder is " + $st.HomeDir
            $u.Action.Content = "Show me the folder"
            $u.Second.Visibility = "Collapsed"
            [void](Copy-ToClipboard $st.HomeDir)
          } else {
            $u.Heading.Text = $st.Name + " is ready to meet you"
            $u.Sub.Text = "One click and you are talking."
            $u.Done1.Text = "Press the button below to say hello. A window will open for the conversation."
            $u.Done2.Text = "From now on there is a 'Talk to your AI' file on your Desktop. Double-click it any time."
            $u.Done3.Text = ""
            $u.Done4.Text = "Its home is " + $st.HomeDir
            $u.Action.Content = "Talk to your AI"
          }
        }
      }
    }
    if ($script:WorkerHandle.IsCompleted -and $st.Phase -eq "working") {
      # the worker stopped without saying why (should not happen; be graceful)
      $st.Phase = "error"
      $st.Failed = $true
      if ($st.Step -ge 1) { $st.StepState[$st.Step] = "soft" }
      $errs = ""
      try { $errs = ($script:Worker.Streams.Error | ForEach-Object { "$_" }) -join " / " } catch { }
      Write-Log ("worker ended unexpectedly: " + $errs)
      $st.Message = "Something did not go as planned. Please tell the person who sent you this, and send them the details (the button below copies them)."
    }
  })
  $timer.Start()

  $w.Add_Closed({
    try { $script:Worker.Stop() } catch { }
    try { $script:Worker.Runspace.Close() } catch { }
  })
  [void]$w.ShowDialog()
}

# ---------------------------------------------------------------------------
# Entry.
# ---------------------------------------------------------------------------
if ($XamlCheck) {
  try {
    $w = New-InstallWindow
    if ($w -and $w.FindName("Action")) { Write-Host "XAML ok: window built (not shown)."; exit 0 }
    Write-Host "XAML loaded but the window is missing its parts."; exit 1
  } catch {
    Write-Host ("XAML check failed: " + $_.Exception.Message)
    if (-not $S.IsWin) { Write-Host "(WPF is Windows-only; run this check on Windows.)" }
    exit 1
  }
}

if ($NoGui -or -not $S.IsWin) {
  if (-not $NoGui) { Write-Host "The window needs Windows; running the steps without it." }
  $S.NoGui = $true
  Write-Host ("Log: " + $S.LogPath)
  Invoke-AllSteps
  if ($S.Failed) { exit 1 }
  if ($S.Mode -eq "claude-code") {
    Write-Host ("Open the Claude app, click Code, and choose this folder: " + $S.HomeDir)
    [void](Copy-ToClipboard $S.HomeDir)
  } elseif ($S.Mode -eq "codex") {
    Write-Host ("Open Codex and choose this folder: " + $S.HomeDir)
  } else {
    Write-Host "To say hello, double-click 'Talk to your AI' on your Desktop."
  }
  exit 0
}

# A WPF window needs a single-threaded apartment. powershell.exe gives us one
# by default; if something odd launched us without it, fall back to the plain
# run rather than crash.
if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -ne "STA") {
  Write-Log "not STA; running without the window."
  $S.NoGui = $true
  Invoke-AllSteps
  if ($S.Failed) { exit 1 } else { exit 0 }
}

try {
  Start-Gui
} catch {
  Write-Log ("window failed: " + $_.Exception.Message)
  # Last resort: no window at all, but still no stack trace on screen.
  $S.NoGui = $true
  Write-Host "The setup window could not open. Running the steps here instead."
  if ($S.Phase -eq "working" -and $S.Step -eq 0) { Invoke-AllSteps }
  if ($S.Failed) { exit 1 }
}
