@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"
set "VENV_PY=venv\Scripts\python.exe"
set "RECRIAR_VENV="
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"

if not exist "%VENV_PY%" set "RECRIAR_VENV=1"
if exist "%VENV_PY%" (
    "%VENV_PY%" --version >nul 2>&1
    if errorlevel 1 set "RECRIAR_VENV=1"
)

if defined RECRIAR_VENV (
    echo Criando ou reparando o ambiente virtual...
    python -m venv --clear venv
    if errorlevel 1 goto :erro
)

echo Instalando ou atualizando dependencias...
if exist "wheelhouse\" (
    "%VENV_PY%" -m pip install --disable-pip-version-check --no-index --find-links=wheelhouse -r requirements.txt
) else (
    "%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
)
if errorlevel 1 goto :erro

if not exist ".env" (
    copy ".env.rede.example" ".env" >nul
    echo.
    echo O arquivo .env foi criado a partir do modelo de rede.
    echo Configure o servidor MySQL, o IP ou DNS do LOGGERAL e uma chave secreta.
    echo Depois execute este arquivo novamente.
    pause
    exit /b 1
)

echo Validando configuracao de rede...
"%VENV_PY%" manage.py verificar_rede
if errorlevel 1 goto :erro

echo Aplicando migrations e preparando o primeiro acesso...
"%VENV_PY%" manage.py preparar_acesso_inicial
if errorlevel 1 goto :erro

"%VENV_PY%" manage.py verificar_banco
if errorlevel 1 goto :erro

echo Validando o motor local LOGGERAL Insight...
"%VENV_PY%" manage.py verificar_insight
if errorlevel 1 goto :erro

echo Preparando arquivos estaticos...
"%VENV_PY%" manage.py collectstatic --noinput
if errorlevel 1 goto :erro

echo.
echo LOGGERAL pronto para a rede corporativa na porta TCP 8000.
echo A TI deve liberar essa porta somente para a rede autorizada.
echo Feche esta janela para encerrar o sistema.
start "" http://127.0.0.1:8000/
"venv\Scripts\waitress-serve.exe" --listen=0.0.0.0:8000 config.wsgi:application
goto :fim

:erro
echo.
echo Nao foi possivel iniciar o LOGGERAL em rede. Revise a mensagem acima.
pause

:fim
endlocal
