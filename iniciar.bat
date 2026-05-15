@echo off
chcp 65001 >nul
title FOPAG
cd /d "%~dp0"

echo.
echo  ================================================
echo   FOPAG - Sistema de Gestao de Cargos - Miracema
echo  ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Python nao encontrado.
    echo  Instale em https://python.org
    pause
    exit /b 1
)

echo  [1/3] Instalando dependencias...
python -m pip install fastapi uvicorn aiofiles openpyxl pandas fpdf2 --quiet --disable-pip-version-check
echo        Feito.
echo.

echo  [2/3] Preparando banco de dados...
python setup.py
if errorlevel 1 (
    echo.
    echo  ERRO ao preparar o banco. Verifique o arquivo erro_log.txt
    pause
    exit /b 1
)
echo.

echo  [3/3] Iniciando servidor...
echo        Abrindo em http://localhost:8000
echo        Feche esta janela para encerrar o sistema.
echo.
python app.py

pause
