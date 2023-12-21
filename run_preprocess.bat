@echo off
echo Starting preprocessing
call conda activate base 
python run_preprocess.py
echo basic files are written
::echo starting parking update
::cd .\parking
::python run.py 2022
::echo parking update Done
pause
call conda deactivate
timeout /nobreak /t 5 >nul
