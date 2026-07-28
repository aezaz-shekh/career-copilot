@echo off
REM ============================================================================
REM  AI Career Co-Pilot - login autostart
REM
REM  Launched by a shortcut in the Windows Startup folder, so the backend and
REM  frontend are already listening whenever you open 127.0.0.1:5173.
REM
REM  Unlike run.bat this does NOT open a browser - you open the tab yourself -
REM  and both windows start minimised so they stay out of the way.
REM
REM  Each server is skipped if its port is already listening, so running this
REM  twice (or running run.bat afterwards) will not start duplicates.
REM
REM  Still 127.0.0.1 only - nothing is exposed to the network.
REM ============================================================================

setlocal
cd /d "%~dp0"

REM --- Ollama on 11434 --------------------------------------------------------
REM  Ollama installs its own Startup shortcut, but it can lag behind us after a
REM  sign-in. Starting it here too means the whole stack is back without waiting.
netstat -ano | findstr ":11434" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "Ollama" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
  )
)

REM --- Backend on 8000 --------------------------------------------------------
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
  if exist "backend\.venv\Scripts\python.exe" (
    start "Career Co-Pilot API" /min cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  )
)

REM --- Frontend on 5173 -------------------------------------------------------
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
  if exist "frontend\node_modules" (
    start "Career Co-Pilot UI" /min cmd /k "cd /d "%~dp0frontend" && npm run dev"
  )
)

endlocal
