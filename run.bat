@echo off
REM ============================================================================
REM  AI Career Co-Pilot - one-command launcher (Windows)
REM
REM  Starts the FastAPI backend and the Vite frontend, each in its own window,
REM  then opens the app in your browser. Close the two windows to stop the app.
REM  Everything runs on 127.0.0.1 only - nothing is exposed to the network.
REM ============================================================================

setlocal
cd /d "%~dp0"

echo ============================================
echo   AI Career Co-Pilot - starting locally
echo ============================================
echo.

REM --- Is Ollama running? (warning only - the Setup tab can guide the fix) ---
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo [!] Ollama does not appear to be running.
  echo     In another terminal run:  ollama serve
  echo     The app still starts - use the Setup tab to finish configuring.
  echo.
)

REM --- Backend ----------------------------------------------------------------
if not exist "backend\.venv\Scripts\python.exe" (
  echo [X] Backend virtualenv not found at backend\.venv
  echo     Create it once:
  echo         cd backend
  echo         python -m venv .venv
  echo         .venv\Scripts\pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)
echo Starting backend on http://127.0.0.1:8000 ...
start "Career Co-Pilot API" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM --- Frontend ---------------------------------------------------------------
if not exist "frontend\node_modules" (
  echo Installing frontend dependencies (first run only) ...
  pushd frontend
  call npm install
  popd
)
echo Starting frontend on http://127.0.0.1:5173 ...
start "Career Co-Pilot UI" cmd /k "cd /d "%~dp0frontend" && npm run dev"

REM --- Open the app once the servers have had a moment to boot -----------------
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:5173

echo.
echo Both servers are launching in their own windows.
echo Close those windows (or press Ctrl+C in each) to stop the app.
echo.
endlocal
