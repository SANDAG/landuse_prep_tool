@echo off
echo Starting parking
call conda activate base 
python run.py 2035
echo basic files are written
call conda deactivate
pause
timeout /nobreak /t 5 >nul
