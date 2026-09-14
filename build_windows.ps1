$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    throw "Ambiente virtual nao encontrado em .\venv. Crie o venv e instale as dependencias antes de gerar o executavel."
}

Write-Host "Atualizando pip e instalando dependencias do projeto..."
Invoke-Checked { .\venv\Scripts\python.exe -m pip install --upgrade pip } "Falha ao atualizar o pip."
Invoke-Checked { .\venv\Scripts\python.exe -m pip install -r requirements.txt } "Falha ao instalar as dependencias."

Write-Host "Coletando arquivos estaticos para entrar no executavel..."
$env:DEBUG = "True"
Invoke-Checked { .\venv\Scripts\python.exe .\manage.py collectstatic --noinput } "Falha ao coletar arquivos estaticos."

Write-Host "Gerando executavel com as dependencias embutidas..."
Invoke-Checked {
    .\venv\Scripts\python.exe -m PyInstaller `
        --noconfirm `
        --clean `
        .\HistoricoNavios.spec
} "Falha ao gerar o executavel."

Write-Host ""
Write-Host "Executavel criado em: $ProjectRoot\dist\HistoricoNavios.exe"
Write-Host "Copie esse arquivo para outra maquina Windows e execute. Nao precisa instalar Python nem pip na maquina de destino."
