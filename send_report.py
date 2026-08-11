"""
rapor.md dosyasini e-posta ile gonderir.

Gmail SMTP kullanir. Kullanmadan once .env dosyasina sunlari ekleyin:

    GMAIL_ADDRESS=sizin_adresiniz@gmail.com
    GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # normal sifre DEGIL, Uygulama Sifresi
    RAPOR_ALICI=alici@ornek.com          # opsiyonel, bos birakilirsa GMAIL_ADDRESS'e gonderilir

Uygulama Sifresi almak icin: https://myaccount.google.com/apppasswords
(Google hesabinizda 2 adimli dogrulama acik olmali.)

Kullanim:
    python send_report.py
    python send_report.py --dosya rapor.md
    python send_report.py --zorla        # tazelik kontrolunu atla
"""
import argparse
import os
import smtplib
import socket
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ciktiyi UTF-8'e sabitle — .bat log dosyasina yonlendirdiginde Python sistem
# yerel kodlamasini (Turkce Windows'ta cp1254) kullanir ve Turkce olmayan
# karakterlerde UnicodeEncodeError verir. Bkz. main.py'deki ayni not.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")

SMTP_SUNUCU = "smtp.gmail.com"
SMTP_PORT = 587

# Rapor bu suredem eskiyse gonderilmez. main.py bir sebeple rapor.md'yi
# guncelleyemediginde (site yapisi degisti, yeni haber yok, ag hatasi)
# duenkuu raporun tekrar gonderilmesini engeller.
TAZELIK_SAAT = 12


def _tazelik_kontrolu(yol: Path, zorla: bool) -> None:
    """rapor.md yeterince taze mi? Degilse gondermeden cikar."""
    if zorla:
        return

    yas = datetime.now() - datetime.fromtimestamp(yol.stat().st_mtime)
    if yas <= timedelta(hours=TAZELIK_SAAT):
        return

    saat = yas.total_seconds() / 3600
    print(
        f"HATA: {yol.name} {saat:.1f} saat once uretilmis "
        f"(sinir: {TAZELIK_SAAT} saat).\n"
        "Muhtemelen main.py bu sabah raporu guncelleyemedi. Eski rapor "
        "gonderilmedi.\n"
        "Yine de gondermek icin: python send_report.py --zorla"
    )
    sys.exit(1)


def raporu_gonder(dosya_yolu: str, zorla: bool = False) -> None:
    gonderen = os.getenv("GMAIL_ADDRESS")
    uygulama_sifresi = os.getenv("GMAIL_APP_PASSWORD")
    alici = os.getenv("RAPOR_ALICI") or gonderen

    if not gonderen or not uygulama_sifresi:
        print(
            "HATA: .env dosyasinda GMAIL_ADDRESS ve GMAIL_APP_PASSWORD tanimli degil.\n"
            "Bir Google Uygulama Sifresi olusturup .env dosyasina ekleyin:\n"
            "https://myaccount.google.com/apppasswords"
        )
        sys.exit(1)

    yol = Path(dosya_yolu)
    if not yol.exists():
        print(f"HATA: {dosya_yolu} bulunamadi. Once main.py calistirilmali.")
        sys.exit(1)

    _tazelik_kontrolu(yol, zorla)

    icerik = yol.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = f"Yapay Zeka Haberleri Raporu - {datetime.now():%d.%m.%Y}"
    msg["From"] = gonderen
    msg["To"] = alici
    msg.set_content(icerik)
    msg.add_attachment(
        icerik.encode("utf-8"),
        maintype="text",
        subtype="markdown",
        filename=yol.name,
    )

    try:
        with smtplib.SMTP(SMTP_SUNUCU, SMTP_PORT, timeout=30) as sunucu:
            sunucu.starttls()
            sunucu.login(gonderen, uygulama_sifresi)
            sunucu.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        print(
            "HATA: Gmail girisi reddedildi. GMAIL_APP_PASSWORD gecerli bir "
            "Uygulama Sifresi olmali (normal hesap sifresi calismaz) ve "
            "hesapta 2 Adimli Dogrulama acik olmali.\n"
            "https://myaccount.google.com/apppasswords"
        )
        sys.exit(1)
    except (socket.gaierror, OSError) as e:
        print(f"HATA: SMTP sunucusuna baglanilamadi ({SMTP_SUNUCU}:{SMTP_PORT}): {e}")
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"HATA: E-posta gonderilemedi: {e}")
        sys.exit(1)

    print(f"Rapor '{alici}' adresine gonderildi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dosya", default="rapor.md")
    parser.add_argument(
        "--zorla",
        action="store_true",
        help=f"Rapor {TAZELIK_SAAT} saatten eski olsa bile gonder.",
    )
    args = parser.parse_args()
    raporu_gonder(args.dosya, zorla=args.zorla)
