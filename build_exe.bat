@echo off
cd /d "%~dp0"
echo Installing build tools...
python -m pip install --upgrade pyinstaller requests keyboard pillow
set ICON=
if exist ria_icon.ico set ICON=--icon ria_icon.ico
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name Ria %ICON% ria.py
echo.
echo Done: dist\Ria.exe
echo Put the ria_*.png images (and optionally settings.json) next to Ria.exe.
pause
