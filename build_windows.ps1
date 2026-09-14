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

$VenvPython = ".\venv\Scripts\python.exe"
$VenvValido = Test-Path $VenvPython
if ($VenvValido) {
    & $VenvPython --version *> $null
    $VenvValido = $LASTEXITCODE -eq 0
}
if (-not $VenvValido) {
    Write-Host "Criando ou reparando o ambiente virtual..."
    python -m venv --clear venv
    if ($LASTEXITCODE -ne 0) {
        throw "Nao foi possivel criar o ambiente virtual com o Python instalado."
    }
}

Write-Host "Atualizando pip e instalando dependencias do projeto..."
Invoke-Checked { & $VenvPython -m pip install --upgrade pip } "Falha ao atualizar o pip."
Invoke-Checked { & $VenvPython -m pip install -r requirements.txt } "Falha ao instalar as dependencias."

Write-Host "Coletando arquivos estaticos para entrar no executavel..."
$env:DEBUG = "True"
Invoke-Checked { & $VenvPython .\manage.py collectstatic --noinput } "Falha ao coletar arquivos estaticos."

Write-Host "Gerando executavel com as dependencias embutidas..."
Invoke-Checked {
    & $VenvPython -m PyInstaller `
        --noconfirm `
        --clean `
        .\HistoricoNavios.spec
} "Falha ao gerar o executavel."

Copy-Item -LiteralPath ".\.env.rede.example" -Destination ".\dist\loggeral.env.example" -Force

Write-Host ""
Write-Host "Executavel criado em: $ProjectRoot\dist\HistoricoNavios.exe"
Write-Host "Modelo de configuracao: $ProjectRoot\dist\loggeral.env.example"
Write-Host "Copie os dois arquivos para outra maquina, renomeie o modelo para .env e configure o MySQL."
Write-Host "Nao e necessario instalar Python nem pip na maquina de destino."
