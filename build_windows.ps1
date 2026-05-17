$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    throw "Ambiente virtual nao encontrado em .\venv. Crie o venv e instale as dependencias antes de gerar o executavel."
}

.\venv\Scripts\python.exe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name HistoricoNavios `
    --add-data "config;config" `
    --add-data "historico\templates;historico\templates" `
    --add-data "historico\static;historico\static" `
    --add-data "estoque\templates;estoque\templates" `
    --add-data "static;static" `
    --add-data "staticfiles;staticfiles" `
    --add-data "media;media" `
    --add-data "db.sqlite3;." `
    --hidden-import "whitenoise.middleware" `
    --hidden-import "whitenoise.storage" `
    desktop_launcher.py

Write-Host ""
Write-Host "Executavel criado em: $ProjectRoot\dist\HistoricoNavios.exe"
Write-Host "Copie esse arquivo para outra maquina Windows e execute."
