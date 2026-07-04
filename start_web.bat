@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Please install Python 3.10+ and run this script again.
  pause
  exit /b 1
)

echo Installing required Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

echo Starting local web app at http://localhost:8501/
python -m streamlit run app.py --server.address localhost --server.port 8501
pause
