@echo off
REM MyGameShelf — double-click launcher. Runs start.ps1 (backend + frontend).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
