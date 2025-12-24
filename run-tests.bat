@echo off
REM 在 Windows cmd 中執行測試
python -m pip install --upgrade pip
pip install pytest
pytest -q
