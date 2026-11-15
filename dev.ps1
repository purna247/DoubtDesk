<#
.SYNOPSIS
    DoubtDesk Developer CLI Runner for PowerShell
.DESCRIPTION
    Wraps python dev.py for 1-command convenience.
.EXAMPLE
    .\dev.ps1 backend
    .\dev.ps1 frontend
    .\dev.ps1 all
#>
param(
    [ValidateSet("backend", "frontend", "all", "worker", "seed")]
    [string]$Service = "backend"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DevPy = Join-Path $ScriptDir "dev.py"

# Use system python or venv python to execute dev.py
$VenvPy = Join-Path $ScriptDir "backend\.venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    & $VenvPy $DevPy $Service
} else {
    python $DevPy $Service
}
