# Jalanin worker Screening AI + auto-reload tiap file .py diubah.
# Pakai: klik kanan > Run with PowerShell, atau di terminal: .\dev.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Error "conda tidak ada di PATH. Buka Anaconda PowerShell atau pastikan conda init sudah jalan."
    exit 1
}

# Muat fungsi conda (biar 'conda activate' jalan walau dijalankan dari shell baru)
(& conda "shell.powershell" "hook") | Out-String | Invoke-Expression
conda activate openai

Write-Host "Env: openai | Watching *.py | Ctrl+C buat stop" -ForegroundColor Green
watchfiles "python -u main.py" .
