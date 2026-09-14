@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 goto :erro
)

echo Instalando ou atualizando dependencias...
"venv\Scripts\python.exe" -m pip install -r requirements.txt
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

"venv\Scripts\python.exe" manage.py preparar_acesso_inicial
if errorlevel 1 goto :erro

"venv\Scripts\python.exe" manage.py verificar_banco
if errorlevel 1 goto :erro

echo.
echo LOGGERAL disponivel em http://127.0.0.1:8000/
echo Feche esta janela para encerrar o sistema.
start "" http://127.0.0.1:8000/
"venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
goto :fim

:erro
echo.
echo Nao foi possivel preparar o LOGGERAL. Revise a mensagem acima.
pause

:fim
endlocal
