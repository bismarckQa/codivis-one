$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python 3.13 no está instalado."
}

py -3.13 -m venv .venv
& .venv\Scripts\python.exe -m pip install --upgrade pip
& .venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
& .venv\Scripts\python.exe scripts\bootstrap_env.py

Write-Host "Entorno listo. Actívalo con .venv\Scripts\Activate.ps1"
