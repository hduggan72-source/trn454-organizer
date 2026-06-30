@echo off
title UGC AI Image Organizer
color 0A
echo.
echo  Checking dependencies...
echo.

pip show flask >nul 2>&1
if errorlevel 1 (
    echo  Installing Flask...
    pip install flask
)

pip show anthropic >nul 2>&1
if errorlevel 1 (
    echo  Installing Anthropic...
    pip install anthropic
)

echo  Starting organizer...
echo.
python "%~dp0ugc_organizer_desktop.py"

if errorlevel 1 (
    echo.
    echo  ERROR: Could not start.
    echo  Make sure Python is installed: https://python.org
    pause
)
