@echo off
rem Starts the Bismarckturm UI without loading your PowerShell profile.
rem The console stays visible so any start-up error can be read.
rem To hide it later, add  -WindowStyle Hidden  after -STA.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0BismarckturmUI.ps1"
if errorlevel 1 pause
