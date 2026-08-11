import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# Makale linklerini menü, etiket ve bölüm linklerinden ayırmak için.
# Ya yolda 4+ haneli bir kimlik vardır (/news/799431/...), ya da yolun sonunda
# en az üç tireli uzun bir slug bulunur (.../yeni-model-duyuruldu-bugun).
MAKALE_DESENI = re.compile(r"/\d{4,}/|[a-z0-9]+(?:-[a-z0-9]+){2,}/?$")

# Ana sayfada haber olmayan bölümler. Ajan 1 zaten editoryal eleme yapıyor;
# burada sadece belirgin olanları ucuza eliyoruz.
DISLANAN_YOLLAR = ("/deals", "/coupons", "/store", "/podcast", "/video",
                   "/newsletter", "/about", "/author", "/tag", "/pages",
                   "/category", "/events")

# Aynı haberin günlerce tekrar raporlanmasını önleyen kalıcı kayıt.
GECMIS_DOSYASI = "gorulen_haberler.json"
GECMIS_GUN = 30


def haber_adaylarini_getir(anasayfa_url: str, limit: int = 25) -> list[dict]:
    """Ana sayfadaki makale linklerini SAYFADAKİ SIRAYLA toplar.

    RSS'ten farkı: sıra kronolojik değil editoryaldir — sayfanın en üstündeki
    haber, sitenin o an en önemli gördüğü haberdir. Ana sayfa HTML'inde yayın
    tarihi bulunmadığı için tarih burada okunmaz; makale sayfasından alınır
    (bkz. haber_icerigini_getir).

    Menü/reklam ayıklamasını Ajan 1 (LLM) yapacağı için bilerek fazla aday bırakılır.
    """
    response = requests.get(anasayfa_url, headers=HEADERS, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    taban_alan = urlparse(anasayfa_url).netloc
    adaylar, gorulen = [], set()

    for baglanti in soup.find_all('a', href=True):
        baslik = baglanti.get_text(strip=True)
        # Kısa metinler menü, etiket ya da "Devamı" tipi linklerdir.
        if len(baslik) < 25:
            continue

        link = urljoin(anasayfa_url, baglanti['href']).split('#')[0]
        parcali = urlparse(link)

        if parcali.netloc != taban_alan:
            continue
        if any(parcali.path.startswith(y) for y in DISLANAN_YOLLAR):
            continue
        if not MAKALE_DESENI.search(parcali.path):
            continue
        # Aynı haber sayfada birden fazla yerde görünebilir; ilk görüldüğü
        # sıra korunur, çünkü editoryal önem sırasını temsil eder.
        if link in gorulen:
            continue

        gorulen.add(link)
        adaylar.append({"baslik": baslik, "link": link})

        if len(adaylar) >= limit:
            break

    return adaylar


def _yayin_tarihi_bul(soup):
    """Makale sayfasından yayın tarihini datetime olarak çıkarır.

    Bulunamazsa None döner; bu normaldir ve hata sayılmaz, sadece rapora
    tarih yazılmaz. Biçimlendirilmiş metin yerine ham datetime döndürmesi
    önemli: "dd.mm.yyyy" metni ay/yıl sınırında yanlış sıralanır.
    """
    # 1) Standart Open Graph / article meta etiketi — en güvenilir kaynak.
    meta = (soup.find('meta', attrs={'property': 'article:published_time'})
            or soup.find('meta', attrs={'name': 'article:published_time'}))
    ham = meta.get('content') if meta else None

    # 2) Yedek: <time datetime="..."> etiketi.
    if not ham:
        etiket = soup.find('time', attrs={'datetime': True})
        ham = etiket['datetime'] if etiket else None

    if not ham:
        return None

    try:
        # Python 3.10 ISO ayrıştırıcısı 'Z' son ekini anlamaz; +00:00'a çeviriyoruz.
        tarih = datetime.fromisoformat(ham.strip().replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None

    if tarih.tzinfo is None:
        tarih = tarih.replace(tzinfo=timezone.utc)
    return tarih


def haber_icerigini_getir(link: str) -> dict:
    """Makalenin gövde metnini ve yayın tarihini TEK istekte çeker.

    Döner: {"icerik": str, "tarih": str, "_yayin": datetime | None}
    `tarih` rapora yazılacak metin (bulunamazsa ""), `_yayin` ise sıralama
    için ham datetime'dır. Alt çizgi, bu alanın ajanlara gönderilmeyeceğini
    (JSON'a serileştirilemez) belirtir.
    """
    try:
        response = requests.get(link, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Tarih, temizlikten ÖNCE okunmalı: meta etiketleri <head> içinde ve
        # decompose() sonrası erişilemez hale gelirler.
        yayin = _yayin_tarihi_bul(soup)

        for etiket in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            etiket.decompose()

        govde = soup.find('article') or soup.find('main') or soup
        paragraflar = [p.get_text(strip=True) for p in govde.find_all('p')]
        metin = "\n".join(p for p in paragraflar if len(p) > 40)

        return {
            # İlk ~4000 karakter sınıflandırma için genelde yeterli.
            "icerik": metin[:4000] or "[İçerik alınamadı — sayfa yapısı tanınamadı]",
            "tarih": yayin.astimezone().strftime("%d.%m.%Y %H:%M") if yayin else "",
            "_yayin": yayin,
        }
    except Exception as e:
        return {"icerik": f"[İçerik çekilemedi: {e}]", "tarih": "", "_yayin": None}


# ============================================================
# Rapor linklerinin doğrulanması
# ============================================================
# Markdown link biçimi: [metin](https://...)
MD_LINK_DESENI = re.compile(r"\[[^\]]*\]\((https?://[^\s)]+)\)")


def raporu_linkleriyle_dogrula(rapor: str, sonuclar: list[dict]) -> tuple[str, list[str]]:
    """Ajan 3'ün yazdığı rapordaki linkleri gerçek haber linkleriyle karşılaştırır.

    Ajan 1'in linklerine güvenmediğimiz gibi (bkz. main.py'deki aday_dizini),
    Ajan 3'ün yazdığı linklere de güvenmiyoruz: LLM bir URL'yi kısaltabilir,
    bozabilir ya da tamamen uydurabilir. Burada iki şeyi garanti altına alıyoruz:

      1. Raporda geçen her link gerçekten analiz edilen haberlere ait.
      2. Hiçbir haber linksiz kalmıyor — eksik kalanlar "Kaynaklar" bölümüne eklenir.

    Döner: (rapor, uyarilar). Ajan işini düzgün yaptıysa rapor değişmeden,
    uyarı listesi de boş döner.
    """
    gecerli = {s["link"] for s in sonuclar}
    bulunan = set(MD_LINK_DESENI.findall(rapor))
    uyarilar = []

    # 1) Uydurulmuş ya da bozulmuş linkler: rapordan silmiyoruz (metnin akışını
    #    bozar), ama konsolda görünür kılıyoruz ki fark edilsin.
    for url in sorted(bulunan - gecerli):
        uyarilar.append(f"raporda tanınmayan link: {url}")

    # 2) Rapora hiç girmemiş haberler için sonuna kaynak listesi ekle.
    eksik = [s for s in sonuclar if s["link"] not in bulunan]
    if eksik:
        uyarilar.append(
            f"{len(eksik)} haberin linki metne eklenmemiş; 'Kaynaklar' bölümü eklendi."
        )
        satirlar = "\n".join(f"- [{s['baslik']}]({s['link']})" for s in eksik)
        rapor = f"{rapor.rstrip()}\n\n## 🔗 Kaynaklar\n\n{satirlar}\n"

    return rapor, uyarilar


# ============================================================
# Tekrar kontrolü — daha önce raporlanmış haberleri hatırlar
# ============================================================
def gecmisi_yukle(dosya: str = GECMIS_DOSYASI) -> dict:
    """Daha önce raporlanmış {link: ilk_raporlama_zamani} kaydını okur.

    GECMIS_GUN'den eski kayıtlar atılır; dosya süresiz büyümesin ve çok eski
    bir haber tekrar ana sayfaya düşerse yeniden raporlanabilsin diye.
    Dosya yoksa veya bozuksa boş sözlük döner (tekrar kontrolü devre dışı kalır,
    program durmaz).
    """
    yol = Path(dosya)
    if not yol.exists():
        return {}
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(veri, dict):
        return {}

    sinir = datetime.now(timezone.utc) - timedelta(days=GECMIS_GUN)
    temiz = {}
    for link, zaman in veri.items():
        try:
            if datetime.fromisoformat(zaman) >= sinir:
                temiz[link] = zaman
        except (TypeError, ValueError):
            continue
    return temiz


def gecmise_ekle(linkler: list[str], gecmis: dict, dosya: str = GECMIS_DOSYASI) -> None:
    """Raporlanan linkleri geçmişe yazar. Zaten varsa ilk tarihi korur."""
    simdi = datetime.now(timezone.utc).isoformat()
    for link in linkler:
        gecmis.setdefault(link, simdi)
    try:
        Path(dosya).write_text(
            json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        # Geçmiş yazılamazsa rapor yine de geçerlidir; sadece uyarıyoruz.
        print(f"UYARI: geçmiş dosyası yazılamadı ({e}). Tekrar kontrolü bu tur atlandı.")
