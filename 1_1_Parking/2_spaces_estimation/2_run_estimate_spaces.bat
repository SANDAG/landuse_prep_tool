@echo off
echo Starting Parking spaces estimation
call conda activate base 
python 2_parking_spaces.py
echo Initial files are written
call conda deactivate
pause