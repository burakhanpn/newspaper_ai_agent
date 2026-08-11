# AI Haber Raporu - gunluk zamanlanmis gorev kurulumu
#
# Kullanim:
#   1. Bu dosyayi sag tiklayin -> "PowerShell ile calistir"
#   VEYA
#   2. PowerShell'i proje klasorunde acip:
#        powershell -ExecutionPolicy Bypass -File .\gorevi_kur.ps1
#
# Klasor yolu sabit degildir; script kendi bulundugu dizini kullanir.
#
# Yonetici yetkisi GEREKMEZ - gorev sadece bu kullanici icin olusturulur.

$ErrorActionPreference = "Stop"

$GorevAdi = "AI Haber Raporu"

# Klasor yolu sabit kodlanmaz: bu script kendi bulundugu dizini kullanir.
# Boylece proje klasoru tasinsa veya yeniden adlandirilsa da calisir.
$Klasor = $PSScriptRoot
if (-not $Klasor) {
    # Nadir durum: script dosyadan degil, panoya yapistirilarak calistirildiysa
    # $PSScriptRoot bos gelir. O zaman icinde bulunulan dizine duseriz.
    $Klasor = (Get-Location).Path
}
$Bat = Join-Path $Klasor "gunluk_rapor_calistir.bat"

# --- Dogrulama ---
if (-not (Test-Path $Bat)) {
    Write-Host "HATA: gunluk_rapor_calistir.bat bulunamadi." -ForegroundColor Red
    Write-Host "Aranan konum: $Bat"
    Write-Host "Bu script'i proje klasorunun icinden calistirdiginizdan emin olun."
    exit 1
}

Write-Host "Proje klasoru: $Klasor" -ForegroundColor DarkGray

# Ayni isimde gorev varsa kaldir (tekrar calistirilabilir olsun diye)
$mevcut = Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue
if ($mevcut) {
    Write-Host "Ayni isimde eski gorev bulundu, guncelleniyor..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false
}

# --- Gorev tanimi ---
$eylem = New-ScheduledTaskAction -Execute $Bat -WorkingDirectory $Klasor

$tetikleyici = New-ScheduledTaskTrigger -Daily -At "09:00"

$ayarlar = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 10)

Register-ScheduledTask `
    -TaskName    $GorevAdi `
    -Action      $eylem `
    -Trigger     $tetikleyici `
    -Settings    $ayarlar `
    -Description "Her sabah 09:00'da WIRED RSS uzerinden AI haber raporu uretir ve e-posta ile gonderir." | Out-Null

Write-Host ""
Write-Host "BASARILI: '$GorevAdi' gorevi olusturuldu." -ForegroundColor Green
Write-Host ""
Get-ScheduledTask -TaskName $GorevAdi |
    Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime, LastRunTime, LastTaskResult |
    Format-List

Write-Host "Hemen test etmek icin:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$GorevAdi'"
Write-Host ""
Write-Host "Sonucu gormek icin klasordeki gunluk_rapor.log dosyasina bakin."
Write-Host "Gorevi kaldirmak icin:" -ForegroundColor Cyan
Write-Host "  Unregister-ScheduledTask -TaskName '$GorevAdi' -Confirm:`$false"
