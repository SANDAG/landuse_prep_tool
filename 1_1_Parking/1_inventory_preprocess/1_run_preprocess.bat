@echo off
echo Starting Reduction and Imputation
call conda activate base 
python 1_parking_preprocess.py
echo preprocessed inventoroy files are written
call conda deactivate
pause