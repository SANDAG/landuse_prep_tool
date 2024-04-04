@echo off
echo Starting Parking Costs estimation
call conda activate base 

python estimate_parking_costs.py

echo Final parking file is written
call conda deactivate
pause