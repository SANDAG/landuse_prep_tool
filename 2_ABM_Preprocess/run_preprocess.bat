@echo off
echo Starting preprocessing
python run_preprocess.py config.yaml
echo basic files are written
pause
timeout /nobreak /t 5 >nul
