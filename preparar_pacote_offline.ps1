$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Wheelhouse = Join-Path $ProjectRoot "wheelhouse"
New-Item -ItemType Directory -Force -Path $Wheelhouse | Out-Null

Write-Host "Baixando dependencias Windows para instalacao sem internet..."
python -m pip download --only-binary=:all: --dest $Wheelhouse -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel montar o pacote offline. Verifique a conexao e as versoes em requirements.txt."
}

Write-Host "Pacote pronto em: $Wheelhouse"
Write-Host "Copie a pasta wheelhouse junto com o projeto para o servidor da empresa."
