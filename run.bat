@echo off
echo.
echo Starting Crossposter...
:loop
python crosspost.py
timeout /t 3600 /nobreak
goto loop