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
"""
import argparse
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SMTP_SUNUCU = "smtp.gmail.com"
SMTP_PORT = 587


def raporu_gonder(dosya_yolu: str) -> None:
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

    with smtplib.SMTP(SMTP_SUNUCU, SMTP_PORT) as sunucu:
        sunucu.starttls()
        sunucu.login(gonderen, uygulama_sifresi)
        sunucu.send_message(msg)

    print(f"Rapor '{alici}' adresine gonderildi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dosya", default="rapor.md")
    args = parser.parse_args()
    raporu_gonder(args.dosya)
