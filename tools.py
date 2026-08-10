import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# RSS'te dc:subject alanı yazının türünü verir. Bunlar haber değil; kupon
# sayfaları ve "en iyi X" alışveriş rehberleri her ay yeniden yayınlandığı için
# tarihleri hep taze görünür ve listeyi doldurur.
# Not: Bu liste WIRED'ın dc:subject taksonomisine göre ayarlanmıştı. Kaynak
# The Verge'e değiştirildi; dc:subject alanı boş/farklı gelirse bu filtre
# hiçbir şeyi elemez — devre dışı kalması zararsızdır, çünkü Ajan 1
# (baslik_okuyucu_ajani) haber olmayan öğeleri zaten editoryal olarak eler.
HABER_OLMAYAN_TURLER = {"Coupons", "Buying Guide", "Product Review"}

_DC = "{http://purl.org/dc/elements/1.1/}"


def haber_adaylarini_getir(rss_url: str, max_saat: int = 48, limit: int = 15) -> list[dict]:
    """RSS akışından (baslik, link, tarih) aday üçlülerini toplar.

    Ana sayfa scraping'i yerine RSS kullanılıyor: ana sayfa editoryal olarak
    dizilidir ve HTML'inde tarih yoktur, bu yüzden haberlerin güncel olduğu
    garanti edilemiyordu. RSS ise yeniden eskiye sıralı gelir ve her öğede
    pubDate bulunur.

    `max_saat`: bundan eski yazılar tamamen elenir.
    Menü/reklam ayıklamasını Ajan 1 (LLM) yapacağı için bilerek fazla aday bırakılır.
    """
    response = requests.get(rss_url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    kok = ET.fromstring(response.content)

    sinir = datetime.now(timezone.utc) - timedelta(hours=max_saat)
    adaylar = []

    for oge in kok.iter('item'):
        baslik = (oge.findtext('title') or "").strip()
        link = (oge.findtext('link') or "").strip()
        ham_tarih = oge.findtext('pubDate')
        if not baslik or not link or not ham_tarih:
            continue

        if (oge.findtext(_DC + 'subject') or "").strip() in HABER_OLMAYAN_TURLER:
            continue

        try:
            yayin = parsedate_to_datetime(ham_tarih)
        except (TypeError, ValueError):
            continue
        if yayin.tzinfo is None:
            yayin = yayin.replace(tzinfo=timezone.utc)

        # RSS yeniden eskiye sıralı: ilk eski öğede durabiliriz.
        if yayin < sinir:
            break

        adaylar.append({
            "baslik": baslik,
            "link": link,
            "tarih": yayin.astimezone().strftime("%d.%m.%Y %H:%M"),
            "_yayin": yayin,
        })

        if len(adaylar) >= limit:
            break

    return adaylar


def haber_icerigini_getir(link: str) -> str:
    """Tek bir makalenin gövde metnini çeker. Genel yöntem: <article>/<main> içindeki
    (yoksa tüm sayfadaki) anlamlı paragrafları birleştirir. Token tasarrufu için kırpar."""
    try:
        response = requests.get(link, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Gövde dışı gürültüyü temizle.
        for etiket in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            etiket.decompose()

        govde = soup.find('article') or soup.find('main') or soup
        paragraflar = [p.get_text(strip=True) for p in govde.find_all('p')]
        metin = "\n".join(p for p in paragraflar if len(p) > 40)

        if not metin:
            return "[İçerik alınamadı — sayfa yapısı tanınamadı]"

        # İlk ~4000 karakter sınıflandırma için genelde yeterli.
        return metin[:4000]
    except Exception as e:
        return f"[İçerik çekilemedi: {e}]"
