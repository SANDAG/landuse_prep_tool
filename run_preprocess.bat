@echo off
echo Starting preprocessing
:: call conda activate base 
python run_preprocess.py
echo Files are written
:: call conda deactivate
timeout /nobreak /t 5 >nul
