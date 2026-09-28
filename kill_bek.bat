@echo off
title BEK - Arret force
echo.
echo Recherche du serveur BEK sur le port 3001...
echo.

set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3001 ^| findstr LISTENING') do (
    echo PID trouve : %%a
    taskkill /PID %%a /F
    set FOUND=1
)

if "%FOUND%"=="0" (
    echo Aucun serveur sur le port 3001.
)

echo.
echo Termine.
pause