@echo off
REM Gunluk AI haber raporu: main.py calistirir, sonra rapor.md'yi e-posta ile gonderir.
REM Task Scheduler bunu her sabah 09:00'da calistiracak.

cd /d "%~dp0"

REM Sanal ortam varsa onu kullan, yoksa sistem python'unu kullan.
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    set PY=python
)

echo [%date% %time%] Rapor uretiliyor... >> gunluk_rapor.log
%PY% main.py >> gunluk_rapor.log 2>&1

if errorlevel 1 (
    echo [%date% %time%] main.py HATA verdi, e-posta gonderilmiyor. >> gunluk_rapor.log
    exit /b 1
)

echo [%date% %time%] Rapor gonderiliyor... >> gunluk_rapor.log
%PY% send_report.py >> gunluk_rapor.log 2>&1

echo [%date% %time%] Tamamlandi. >> gunluk_rapor.log
