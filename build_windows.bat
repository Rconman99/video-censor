@echo off
setlocal

set APP_NAME=VideoCensor
set VERSION=1.0.0

echo === Building %APP_NAME% v%VERSION% for Windows ===

:: Clean previous builds
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

:: Check Python
python --version
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    exit /b 1
)

:: Install dependencies
echo === Installing dependencies ===
pip install -r requirements.txt
pip install pyinstaller

:: Build with PyInstaller
echo === Building executable ===
pyinstaller VideoCensor-windows.spec --noconfirm

:: Check if build succeeded
if not exist "dist\VideoCensor\VideoCensor.exe" (
    echo ERROR: Build failed - executable not created
    exit /b 1
)

echo === Build complete ===
echo Output: dist\VideoCensor\VideoCensor.exe

:: Create ZIP for distribution
echo === Creating ZIP archive ===
powershell Compress-Archive -Path "dist\VideoCensor\*" -DestinationPath "dist\VideoCensor-%VERSION%-windows.zip" -Force

echo === Done ===
echo Installer: dist\VideoCensor-%VERSION%-windows.zip

pause
