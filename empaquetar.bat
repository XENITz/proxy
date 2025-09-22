@echo off
echo Empaquetando Simple Proxy Manager...

:: Activar el entorno virtual
call .venv\Scripts\activate

:: Instalar PyInstaller si no está instalado
pip install pyinstaller

:: Empaquetar la aplicación
pyinstaller --noconfirm --onefile --windowed ^
  --name "Simple Proxy Manager" ^
  --icon=icon.ico ^
  --add-data "README.md;." ^
  --add-data "icon.ico;." ^
  --hidden-import=PySide6.QtSvg ^
  --hidden-import=PySide6.QtXml ^
  proxy_app.py

echo Empaquetado completado.
echo El ejecutable se encuentra en la carpeta "dist".
pause