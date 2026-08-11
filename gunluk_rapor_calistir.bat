@echo off
REM Gunluk AI haber raporu: main.py calistirir, sonra rapor.md'yi e-posta ile gonderir.
REM Task Scheduler bunu her sabah 09:00'da calistiracak.
REM
REM main.py cikis kodlari:
REM   0 = yeni rapor.md yazildi, gonderilebilir
REM   1 = gercek hata; rapor uretilemedi
REM   2 = hata degil ama yeni haber yok; gonderilecek yeni rapor da yok
REM
REM Bu dosyanin kendi cikis kodu Task Scheduler'da LastTaskResult olarak
REM gorunur. 0 disinda bir deger dondurmesi, sorunu fark edebilmen icin sart.

cd /d "%~dp0"

REM Sanal ortam varsa onu kullan, yoksa sistem python'unu kullan.
if exist ".venv\Scripts\python.exe" (
    set PY=.venv\Scripts\python.exe
) else (
    set PY=python
)

echo. >> gunluk_rapor.log
echo [%date% %time%] === Calisma basladi === >> gunluk_rapor.log

REM ---- 1) Raporu uret ----
%PY% main.py >> gunluk_rapor.log 2>&1
set MAIN_KOD=%errorlevel%

if "%MAIN_KOD%"=="2" (
    echo [%date% %time%] Yeni haber yok; rapor guncellenmedi, e-posta gonderilmiyor. >> gunluk_rapor.log
    exit /b 0
)

if not "%MAIN_KOD%"=="0" (
    echo [%date% %time%] HATA: main.py basarisiz oldu ^(kod %MAIN_KOD%^). E-posta gonderilmiyor. >> gunluk_rapor.log
    exit /b 1
)

REM ---- 2) Raporu gonder ----
echo [%date% %time%] Rapor gonderiliyor... >> gunluk_rapor.log
%PY% send_report.py >> gunluk_rapor.log 2>&1
set SEND_KOD=%errorlevel%

if not "%SEND_KOD%"=="0" (
    echo [%date% %time%] HATA: send_report.py basarisiz oldu ^(kod %SEND_KOD%^). >> gunluk_rapor.log
    exit /b 1
)

echo [%date% %time%] === Tamamlandi === >> gunluk_rapor.log
exit /b 0
