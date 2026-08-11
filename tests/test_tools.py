"""tools.py testleri: aday ayiklama, tarih ayristirma, rapor dogrulama, gecmis."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from bs4 import BeautifulSoup

import tools


# ============================================================
# Aday ayiklama — hangi linkler makale sayilir?
# ============================================================
def _sayfa(linkler):
    """Verilen (metin, href) ikililerinden minimal bir HTML sayfasi kurar."""
    etiketler = "".join(f'<a href="{h}">{m}</a>' for m, h in linkler)
    return f"<html><body>{etiketler}</body></html>"


@pytest.mark.parametrize("yol, beklenen", [
    ("/2026/08/10/google-play-adds-venmo-as-a-payment-option/", True),
    ("/2026/08/09/the-ai-safety-test-is-becoming-a-safety-risk/", True),
    ("/author/mary-ann-azevedo/", False),      # DISLANAN_YOLLAR
    ("/category/artificial-intelligence/", False),
    ("/events/disrupt-2026/", False),
    ("/podcast/equity-crypto-and-ai/", False),
    ("/", False),                              # ana sayfa
    ("/latest/", False),                       # tek kelime, desen tutmaz
    ("/startups/", False),
])
def test_makale_deseni_ve_dislanan_yollar(yol, beklenen):
    dislandi = any(yol.startswith(y) for y in tools.DISLANAN_YOLLAR)
    eslesti = bool(tools.MAKALE_DESENI.search(yol))
    assert ((not dislandi) and eslesti) is beklenen


def test_kisa_baslikli_linkler_elenir(monkeypatch):
    """25 karakterden kisa bag metinleri menu/etiket sayilir."""
    html = _sayfa([
        ("AI", "https://ornek.com/2026/08/10/kisa-baslik-elenmeli/"),
        ("Bu yeterince uzun bir haber basligidir",
         "https://ornek.com/2026/08/10/uzun-baslik-gecmeli/"),
    ])
    _sahte_get(monkeypatch, html)
    adaylar = tools.haber_adaylarini_getir("https://ornek.com/")
    assert [a["baslik"] for a in adaylar] == ["Bu yeterince uzun bir haber basligidir"]


def test_dis_alan_adi_elenir(monkeypatch):
    html = _sayfa([
        ("Baska siteye giden yeterince uzun baslik",
         "https://baskasite.com/2026/08/10/haber-basligi-burada/"),
        ("Ayni siteye giden yeterince uzun baslik",
         "https://ornek.com/2026/08/10/haber-basligi-burada/"),
    ])
    _sahte_get(monkeypatch, html)
    adaylar = tools.haber_adaylarini_getir("https://ornek.com/")
    assert len(adaylar) == 1
    assert "ornek.com" in adaylar[0]["link"]


def test_tekrarlanan_link_bir_kez_alinir(monkeypatch):
    """Ayni haber sayfada birden fazla yerde gorunebilir; ilk sirasi korunur."""
    link = "https://ornek.com/2026/08/10/ayni-haber-iki-kez-gecer/"
    html = _sayfa([
        ("Ayni haber birinci gorunumu burada", link),
        ("Ayni haber ikinci gorunumu burada", link),
    ])
    _sahte_get(monkeypatch, html)
    adaylar = tools.haber_adaylarini_getir("https://ornek.com/")
    assert len(adaylar) == 1


def test_limit_uygulanir(monkeypatch):
    html = _sayfa([
        (f"Yeterince uzun bir haber basligi numara {i}",
         f"https://ornek.com/2026/08/10/haber-numarasi-{i}-burada/")
        for i in range(30)
    ])
    _sahte_get(monkeypatch, html)
    assert len(tools.haber_adaylarini_getir("https://ornek.com/", limit=5)) == 5


def _sahte_get(monkeypatch, html):
    class Yanit:
        text = html
        content = html.encode()
        def raise_for_status(self): pass
    monkeypatch.setattr(tools.requests, "get", lambda *a, **k: Yanit())


# ============================================================
# Yayin tarihi ayristirma
# ============================================================
def test_tarih_meta_etiketinden_okunur():
    soup = BeautifulSoup(
        '<meta property="article:published_time" content="2026-08-10T21:31:00+00:00">',
        "html.parser")
    assert tools._yayin_tarihi_bul(soup).year == 2026


def test_tarih_time_etiketinden_okunur():
    """Meta yoksa <time datetime> yedegi devreye girer."""
    soup = BeautifulSoup('<time datetime="2026-08-10T21:31:00Z">dun</time>', "html.parser")
    t = tools._yayin_tarihi_bul(soup)
    assert t is not None and t.tzinfo is not None


def test_z_soneki_desteklenir():
    """Python 3.10 fromisoformat 'Z' anlamaz; kod +00:00'a cevirmeli."""
    soup = BeautifulSoup(
        '<meta property="article:published_time" content="2026-08-10T21:31:00Z">',
        "html.parser")
    assert tools._yayin_tarihi_bul(soup) is not None


def test_saat_dilimsiz_tarih_utc_sayilir():
    soup = BeautifulSoup(
        '<meta property="article:published_time" content="2026-08-10T21:31:00">',
        "html.parser")
    assert tools._yayin_tarihi_bul(soup).tzinfo == timezone.utc


def test_tarih_bulunamazsa_none_doner():
    """Tarihin olmamasi hata degil, sadece bilgi eksikligidir."""
    assert tools._yayin_tarihi_bul(BeautifulSoup("<p>metin</p>", "html.parser")) is None


def test_bozuk_tarih_none_doner():
    soup = BeautifulSoup(
        '<meta property="article:published_time" content="bu bir tarih degil">',
        "html.parser")
    assert tools._yayin_tarihi_bul(soup) is None


# ============================================================
# Rapor link dogrulama
# ============================================================
SONUCLAR = [
    {"baslik": "Haber A", "link": "https://ornek.com/a/"},
    {"baslik": "Haber B", "link": "https://ornek.com/b/"},
]


def test_tum_linkler_varsa_rapor_degismez():
    rapor = ("**A** [git](https://ornek.com/a/)\n"
             "**B** [git](https://ornek.com/b/)")
    yeni, uyarilar = tools.raporu_linkleriyle_dogrula(rapor, SONUCLAR)
    assert yeni == rapor
    assert uyarilar == []


def test_eksik_link_kaynaklar_bolumu_olarak_eklenir():
    rapor = "**A** [git](https://ornek.com/a/)\n**B** linksiz kaldi"
    yeni, uyarilar = tools.raporu_linkleriyle_dogrula(rapor, SONUCLAR)
    assert "Kaynaklar" in yeni
    assert "https://ornek.com/b/" in yeni
    assert len(uyarilar) == 1


def test_uydurma_link_uyari_verir():
    """Ajan 3'un uydurdugu link rapordan silinmez ama gorunur kilinir."""
    rapor = ("**A** [git](https://ornek.com/UYDURMA/)\n"
             "**B** [git](https://ornek.com/b/)")
    _, uyarilar = tools.raporu_linkleriyle_dogrula(rapor, SONUCLAR)
    assert any("tanınmayan link" in u for u in uyarilar)


def test_hic_link_yoksa_hepsi_eklenir():
    yeni, _ = tools.raporu_linkleriyle_dogrula("**A** aciklama\n**B** aciklama", SONUCLAR)
    assert yeni.count("https://ornek.com/") == 2


# ============================================================
# Rapor bicim dogrulama — "dogru turden belge mi?"
# ============================================================
SAGLIKLI_RAPOR = """# Teknoloji Haberleri Raporu

## Yapay Zeka Gundemi

**OpenAI yeni siber guvenlik modelini duyurdu**
Sirket, yapay zeka destekli saldirilara karsi gelistirdigi yeni modeli tanitti.
Haberin merkezinde otonom ajanlarin savunma amacli kullanimi yer aliyor.
[Habere git](https://ornek.com/a/)

**Rippling karsi dava acti**
Anlasmazligin temelinde MCP standardi bulunuyor.
[Habere git](https://ornek.com/b/)

## Genel Degerlendirme
Gundem guvenlik ekseninde yogunlasiyor ve sektorun savunma tarafina yatirim
yaptigi goruluyor. Bu egilimin surmesi bekleniyor."""


def test_saglikli_rapor_kabul_edilir():
    assert tools.raporu_bicim_dogrula(SAGLIKLI_RAPOR, SONUCLAR) == []


def test_siniflandirma_denetimi_reddedilir():
    """Gercek vaka: Ajan 2'nin promptu yanlislikla Ajan 3'e yapistirildiginda
    olusan cikti. Bicimsel olarak kusursuzdu ama yanlis turden belgeydi."""
    bozuk = """# Degerlendirme

**4. "Sergey Brin has now spent $100 million"**
**HAYIR - Madde 4 (haric tutma):** Kisinin sirketten bagimsiz kampanyasi. Etiket dogru.
[git](https://ornek.com/a/)

**5. "Claude agent hacked into a gym"**
**EVET - Madde 1:** AI ajaninin sisteme sizmasi olayi. Etiket dogru.
[git](https://ornek.com/b/)"""
    sorunlar = tools.raporu_bicim_dogrula(bozuk, SONUCLAR)
    assert any("denetimi" in s for s in sorunlar)


def test_turkce_karakterli_denetim_de_reddedilir():
    """Ayni cikti, Turkce karakterler bozulmadan gelirse de yakalanmali."""
    bozuk = """# Değerlendirme

**HAYIR — Madde 4:** Kişinin şirketten bağımsız kampanyası. Etiket doğru.
[git](https://ornek.com/a/)

**EVET — Madde 1:** AI ajanının sisteme sızması. Etiket doğru.
[git](https://ornek.com/b/)"""
    assert tools.raporu_bicim_dogrula(bozuk, SONUCLAR) != []


def test_evet_hayir_atifli_denetim_reddedilir():
    bozuk = """## Degerlendirme

**1. "OpenAI tender offer" - EVET**
Gerekce: EVET-3 - Ana isi yapay zeka olan sirketin sermaye islemi.
[git](https://ornek.com/a/)

**4. "Aptoide app store" - HAYIR**
Gerekce: HAYIR-3 - Genel teknoloji haberi.
[git](https://ornek.com/b/)

**Sonuc:** Sunulan siniflandirmalarin tamami dogru."""
    assert tools.raporu_bicim_dogrula(bozuk, SONUCLAR) != []


def test_haberde_gecen_madde_ifadesi_yanlis_alarm_vermez():
    """Bir yasa haberi dogal olarak 'Madde 4' diyebilir; tek sinyal tetiklememeli."""
    rapor = SAGLIKLI_RAPOR.replace(
        "MCP standardi bulunuyor.",
        "yeni yasanin 4. maddesi bulunuyor. Madde 4 seffaflik yukumlulugu getiriyor.")
    assert tools.raporu_bicim_dogrula(rapor, SONUCLAR) == []


def test_hic_gecerli_link_yoksa_reddedilir():
    rapor = SAGLIKLI_RAPOR.replace("https://ornek.com/a/", "x").replace(
        "https://ornek.com/b/", "y")
    assert any("link" in s for s in tools.raporu_bicim_dogrula(rapor, SONUCLAR))


def test_asiri_kisa_rapor_reddedilir():
    assert any("kısa" in s for s in tools.raporu_bicim_dogrula("# Rapor\n\nYok.", SONUCLAR))


# ============================================================
# Gecmis kaydi (arsiv)
# ============================================================
def test_gecmis_eski_kayitlari_budar(tmp_path):
    dosya = tmp_path / "gecmis.json"
    eski = (datetime.now(timezone.utc) - timedelta(days=tools.GECMIS_GUN + 5)).isoformat()
    yeni = datetime.now(timezone.utc).isoformat()
    dosya.write_text(json.dumps({"eski": eski, "yeni": yeni}), encoding="utf-8")

    gecmis = tools.gecmisi_yukle(str(dosya))
    assert "yeni" in gecmis and "eski" not in gecmis


def test_bozuk_gecmis_dosyasi_programi_durdurmaz(tmp_path):
    dosya = tmp_path / "gecmis.json"
    dosya.write_text("{bu gecerli json degil", encoding="utf-8")
    assert tools.gecmisi_yukle(str(dosya)) == {}


def test_olmayan_gecmis_dosyasi_bos_doner(tmp_path):
    assert tools.gecmisi_yukle(str(tmp_path / "yok.json")) == {}


def test_gecmise_ekleme_ilk_tarihi_korur(tmp_path):
    dosya = tmp_path / "gecmis.json"
    tools.gecmise_ekle(["https://ornek.com/a/"], {}, str(dosya))
    ilk = json.loads(dosya.read_text(encoding="utf-8"))["https://ornek.com/a/"]

    gecmis = tools.gecmisi_yukle(str(dosya))
    tools.gecmise_ekle(["https://ornek.com/a/", "https://ornek.com/b/"], gecmis, str(dosya))
    son = json.loads(dosya.read_text(encoding="utf-8"))

    assert son["https://ornek.com/a/"] == ilk   # ilk gorulme tarihi degismedi
    assert "https://ornek.com/b/" in son
