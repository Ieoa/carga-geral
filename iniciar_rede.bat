@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 goto :erro
)

echo Instalando ou atualizando dependencias...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
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
"venv\Scripts\python.exe" manage.py verificar_rede
if errorlevel 1 goto :erro

echo Aplicando migrations e preparando o primeiro acesso...
"venv\Scripts\python.exe" manage.py preparar_acesso_inicial
if errorlevel 1 goto :erro

"venv\Scripts\python.exe" manage.py verificar_banco
if errorlevel 1 goto :erro

echo Preparando arquivos estaticos...
"venv\Scripts\python.exe" manage.py collectstatic --noinput
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
