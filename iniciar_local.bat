@echo off
setlocal
cd /d "%~dp0"
set "VENV_PY=venv\Scripts\python.exe"
set "RECRIAR_VENV="

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
    copy ".env.example" ".env" >nul
    echo.
    echo O arquivo .env foi criado.
    echo Configure DATABASE_URL com o usuario, senha e servidor MySQL da empresa.
    echo Depois execute este arquivo novamente.
    pause
    exit /b 1
)

"%VENV_PY%" manage.py preparar_acesso_inicial
if errorlevel 1 goto :erro

"%VENV_PY%" manage.py verificar_banco
if errorlevel 1 goto :erro

echo.
echo LOGGERAL disponivel em http://127.0.0.1:8000/
echo Feche esta janela para encerrar o sistema.
start "" http://127.0.0.1:8000/
"%VENV_PY%" manage.py runserver 127.0.0.1:8000 --noreload
goto :fim

:erro
echo.
echo Nao foi possivel preparar o LOGGERAL. Revise a mensagem acima.
pause

:fim
endlocal
