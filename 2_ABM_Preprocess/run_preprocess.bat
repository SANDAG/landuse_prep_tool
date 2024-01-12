@echo off
echo Starting preprocessing
call conda activate base 
python run_preprocess.py config.yaml
echo basic files are written
call conda deactivate
pause
timeout /nobreak /t 5 >nul
