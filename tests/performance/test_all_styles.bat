@echo off
echo === Testing NIT ===
python tests\performance\debug_opponent_modeling.py --style nit --hands 100 2>&1 | findstr /C:"VPIP" /C:"PFR" /C:"AF:" /C:"WTSD" /C:"W$SD"
echo.

echo === Testing CALLING_STATION ===
python tests\performance\debug_opponent_modeling.py --style calling_station --hands 100 2>&1 | findstr /C:"VPIP" /C:"PFR" /C:"AF:" /C:"WTSD" /C:"W$SD"
echo.

echo === Testing MANIAC ===
python tests\performance\debug_opponent_modeling.py --style maniac --hands 100 2>&1 | findstr /C:"VPIP" /C:"PFR" /C:"AF:" /C:"WTSD" /C:"W$SD"
echo.

echo === Testing FISH ===
python tests\performance\debug_opponent_modeling.py --style fish --hands 100 2>&1 | findstr /C:"VPIP" /C:"PFR" /C:"AF:" /C:"WTSD" /C:"W$SD"
