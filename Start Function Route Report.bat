@echo off
setlocal

cd /d "%~dp0"

echo Starting Function Route Report...
echo.
echo If the browser does not open automatically, visit:
echo http://localhost:8501
echo.

python -m streamlit run app.py --server.headless false

endlocal
