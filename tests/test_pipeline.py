"""main.py testleri: tarihe gore secim ve cikis kodlari.

Ag ve LLM cagrilari monkeypatch ile degistirilir; testler API anahtari
gerektirmez ve internet erisimi olmadan calisir.
"""
from datetime import datetime, timedelta, timezone

import pytest

import main


@pytest.fixture
def sahte_pipeline(monkeypatch, tmp_path):
    """Ag ve ajan cagrilarini taklit eder, calisma dizinini gecici yapar.

    Doner: sayfadaki haberleri (baslik, link, yayin_tarihi) olarak tanimlamaya
    yarayan bir kurucu fonksiyon.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    def kur(sayfa):
        dizin = {link: yayin for _, link, yayin in sayfa}

        monkeypatch.setattr(main, "haber_adaylarini_getir",
                            lambda url, **k: [{"baslik": b, "link": l} for b, l, _ in sayfa])
        monkeypatch.setattr(main, "haber_icerigini_getir", lambda link: {
            "icerik": "govde metni",
            "tarih": dizin[link].astimezone().strftime("%d.%m.%Y %H:%M") if dizin[link] else "",
            "_yayin": dizin[link],
        })
        # Ajan 1: hicbir seyi elemez, havuz sinirina kadar hepsini dondurur
        monkeypatch.setattr(main, "baslik_okuyucu_ajani",
                            lambda adaylar, adet: [{"baslik": a["baslik"], "link": a["link"]}
                                                   for a in adaylar][:adet])
        monkeypatch.setattr(main, "icerik_inceleyici_ajani",
                            lambda b, i: {"ai_ile_ilgili": True, "aciklama": "test"})
        # Ajan 3: bicim denetiminden gecebilecek kadar gercekci bir rapor
        monkeypatch.setattr(main, "rapor_hazirlayici_ajani", lambda s: (
            "# Haber Raporu\n\n## Yapay Zeka Gundemi\n\n"
            + "\n\n".join(f"**{x['baslik']}**\nBu haber hakkinda aciklayici bir "
                          f"paragraf metni burada yer aliyor ve yeterince uzun.\n"
                          f"[Habere git]({x['link']})" for x in s)
            + "\n\n## Genel Degerlendirme\nGundem hakkinda kisa bir degerlendirme."))
        return tmp_path

    return kur


def _saat_once(n):
    return datetime.now(timezone.utc) - timedelta(hours=n)


def _rapordaki_linkler(tmp_path):
    icerik = (tmp_path / "rapor.md").read_text(encoding="utf-8")
    from tools import MD_LINK_DESENI
    return MD_LINK_DESENI.findall(icerik)


# ============================================================
# Tarihe gore secim — projenin can damari
# ============================================================
def test_sayfa_sirasi_degil_yayin_tarihi_belirler(sahte_pipeline):
    """Ana sayfa editoryaldir: one cikarilan ESKI haber en ustte olabilir.

    Bu test sayfayi bilerek ters kurar (en eski en ustte) ve secimin sayfa
    sirasini degil gercek tarihi izledigini dogrular.
    """
    sayfa = [(f"Eski one cikan haber {i}", f"https://ornek.com/eski{i}/", _saat_once(100 - i))
             for i in range(5)]
    sayfa += [(f"Taze haber {i}", f"https://ornek.com/taze{i}/", _saat_once(5 - i))
              for i in range(5)]
    tmp = sahte_pipeline(sayfa)

    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_BASARILI

    linkler = _rapordaki_linkler(tmp)
    assert all("taze" in l for l in linkler), f"eski haber sizdi: {linkler}"


def test_tarihsiz_haberler_sona_alinir(sahte_pipeline):
    """Tarihi okunamayan bir haberin 'en yeni' oldugu iddia edilemez."""
    sayfa = [("Tarihi okunamayan haber burada", "https://ornek.com/tarihsiz/", None)]
    sayfa += [(f"Tarihli haber {i}", f"https://ornek.com/tarihli{i}/", _saat_once(i + 1))
              for i in range(main.HABER_ADEDI)]
    tmp = sahte_pipeline(sayfa)

    with pytest.raises(SystemExit):
        main.main()
    assert not any("tarihsiz" in l for l in _rapordaki_linkler(tmp))


def test_havuz_yetersizse_tarihsiz_haber_de_alinir(sahte_pipeline):
    """Secilecek yeterli tarihli haber yoksa tarihsizler listeyi doldurur."""
    sayfa = [("Tarihi okunamayan haber burada", "https://ornek.com/tarihsiz/", None),
             ("Tarihli tek haber burada", "https://ornek.com/tarihli/", _saat_once(1))]
    tmp = sahte_pipeline(sayfa)

    with pytest.raises(SystemExit):
        main.main()
    assert len(_rapordaki_linkler(tmp)) == 2


def test_ayni_haberler_tekrar_calistirmada_da_secilir(sahte_pipeline):
    """Tekrar filtresi bilerek kaldirildi.

    Eskiden gecmisteki linkler elenirdi; bu, ayni gun ikinci calistirmada
    gunun taze haberlerini eleyip pipeline'i gunler oncesine itiyordu.
    """
    sayfa = [(f"Haber {i}", f"https://ornek.com/h{i}/", _saat_once(i + 1)) for i in range(8)]
    tmp = sahte_pipeline(sayfa)

    with pytest.raises(SystemExit):
        main.main()
    birinci = _rapordaki_linkler(tmp)

    with pytest.raises(SystemExit):
        main.main()
    ikinci = _rapordaki_linkler(tmp)

    assert birinci == ikinci


def test_gecmis_dosyasi_yine_de_yazilir(sahte_pipeline):
    """Filtreleme yok ama arsiv kaydi devam ediyor."""
    sayfa = [(f"Haber {i}", f"https://ornek.com/h{i}/", _saat_once(i + 1)) for i in range(3)]
    tmp = sahte_pipeline(sayfa)

    with pytest.raises(SystemExit):
        main.main()
    assert (tmp / "gorulen_haberler.json").exists()


# ============================================================
# Cikis kodlari — .bat bunlara bakarak e-posta gonderir
# ============================================================
def test_basarili_calisma_sifir_doner(sahte_pipeline):
    tmp = sahte_pipeline([("Yeterince uzun baslik", "https://ornek.com/a/", _saat_once(1))])
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_BASARILI
    assert (tmp / "rapor.md").exists()


def test_ag_hatasi_kod_bir_doner(sahte_pipeline, monkeypatch):
    """Duz `return` cikis kodunu 0 yapar ve .bat dunku raporu yeniden gonderir."""
    sahte_pipeline([])
    monkeypatch.setattr(main, "haber_adaylarini_getir",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ag yok")))
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_HATA


def test_hic_aday_bulunamazsa_kod_bir_doner(sahte_pipeline, monkeypatch):
    sahte_pipeline([])
    monkeypatch.setattr(main, "haber_adaylarini_getir", lambda *a, **k: [])
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_HATA


def test_ajan_gecerli_haber_secemezse_kod_bir_doner(sahte_pipeline, monkeypatch):
    sahte_pipeline([("Yeterince uzun baslik", "https://ornek.com/a/", _saat_once(1))])
    # Ajan taninmayan link dondurur -> aday_dizini'nde bulunamaz
    monkeypatch.setattr(main, "baslik_okuyucu_ajani",
                        lambda a, adet: [{"baslik": "X", "link": "https://uydurma.com/x/"}])
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_HATA


def test_api_anahtari_yoksa_kod_bir_doner(sahte_pipeline, monkeypatch):
    sahte_pipeline([("Yeterince uzun baslik", "https://ornek.com/a/", _saat_once(1))])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_HATA


def test_bozuk_rapor_kaydedilmez_ve_kod_bir_doner(sahte_pipeline, monkeypatch):
    """Bicim denetimi dusunce rapor.md yazilmamali.

    Boylece bir onceki gunun gecerli raporu korunur ve send_report.py
    tazelik kontrolune takilir.
    """
    tmp = sahte_pipeline([("Yeterince uzun baslik", "https://ornek.com/a/", _saat_once(1))])
    monkeypatch.setattr(main, "rapor_hazirlayici_ajani", lambda s: (
        "# Degerlendirme\n\n**EVET - Madde 1:** Etiket dogru.\n"
        "**HAYIR - Madde 3:** Etiket dogru.\n"
        "**Sonuc:** Siniflandirmalarin tamami dogru."))
    with pytest.raises(SystemExit) as e:
        main.main()
    assert e.value.code == main.CIKIS_HATA
    assert not (tmp / "rapor.md").exists()


def test_alt_bilgi_tarih_araligini_icerir(sahte_pipeline):
    tmp = sahte_pipeline([
        ("Yeni haber basligi burada", "https://ornek.com/a/", _saat_once(1)),
        ("Eski haber basligi burada", "https://ornek.com/b/", _saat_once(30)),
    ])
    with pytest.raises(SystemExit):
        main.main()
    assert "Haber aralığı" in (tmp / "rapor.md").read_text(encoding="utf-8")
