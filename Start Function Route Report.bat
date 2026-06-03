@echo off
setlocal

cd /d "%~dp0"

echo Starting Function Route Report...
echo.
echo If the browser does not open automatically, visit:
echo http://localhost:8501
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -m streamlit run app.py --server.headless false
) else (
    python -m streamlit run app.py --server.headless false
)

if errorlevel 1 (
    echo.
    echo Function Route Report failed to start.
    echo Please keep this window open and check the error message above.
    echo.
    pause
)

endlocal
