@echo off
echo Iniciando Simple Proxy Manager...
echo.

REM Activar el entorno virtual
call .venv\Scripts\activate.bat

REM Ejecutar la aplicación
python proxy_app.py

REM Desactivar el entorno virtual al salir
deactivate