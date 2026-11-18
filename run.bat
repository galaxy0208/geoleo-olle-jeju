@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
echo [1/3] Creating environment. First run takes a few minutes...
python -m venv .venv
if errorlevel 1 goto nopython
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto noinstall
:run
where ollama >nul 2>&1
if errorlevel 1 (
  echo [2/3] Ollama not found. Running without LLM.
) else (
  echo [2/3] Ollama found.
  start "" /min ollama serve
)
echo [3/3] Opening the app in your browser. Close this window to stop.
".venv\Scripts\python.exe" -m streamlit run app\ui.py --browser.gatherUsageStats false
goto end
:nopython
echo Python not found. See README.
goto end
:noinstall
echo Package install failed. Check internet connection, then delete the .venv folder and run again.
:end
pause
