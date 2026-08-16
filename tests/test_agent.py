"""agent.py testleri: yanit denetimi, secim cozumleme ve prompt sozlesmeleri.

Bu dosya v1'in kor noktasini kapatir. test_pipeline.py ucu ajani da monkeypatch
ettigi icin agent.py'nin yanit ayristirma yolu hicbir testle calistirilmiyordu:
bos content (refusal), kesik JSON, yanlis fonksiyona yapistirilmis prompt —
sahte bir response nesnesiyle kolayca yakalanabilecek durumlarin hepsi
testlerden sorunsuz geciyordu.

Buradaki testler ag ya da API anahtari gerektirmez; messages.create taklit
edilir ve gonderilen istek yakalanir.
"""
import json

import pytest

import agent
from agent import AjanHatasi


# ============================================================
# Sahte yanit nesneleri
# ============================================================
class _Blok:
    def __init__(self, type, text=""):
        self.type = type
        self.text = text


class _Ayrinti:
    def __init__(self, category):
        self.category = category


class _Yanit:
    def __init__(self, bloklar, stop_reason="end_turn", stop_details=None):
        self.content = bloklar
        self.stop_reason = stop_reason
        self.stop_details = stop_details


def _metin_yaniti(metin):
    return _Yanit([_Blok("text", metin)])


def _secim_yaniti(numaralar):
    return _metin_yaniti(json.dumps({"secimler": numaralar}))


@pytest.fixture
def sahte_cagri(monkeypatch):
    """messages.create'i taklit eder; gonderilen istegi dict olarak dondurur."""
    kayit = {}

    def kur(yanit):
        class _Messages:
            def create(self, **istek):
                kayit.clear()
                kayit.update(istek)
                return yanit

        class _Client:
            messages = _Messages()

        monkeypatch.setattr(agent, "_get_client", lambda: _Client())
        return kayit

    return kur


@pytest.fixture
def adaylar():
    return [{"baslik": f"Haber {i}", "link": f"https://ornek.com/h{i}/"}
            for i in range(6)]


# ============================================================
# Yanit denetimi — uc sessiz basarisizligin kapandigi yer
# ============================================================
def test_reddedilen_istek_ajanhatasi_firlatir():
    """Opus 5'in siniflandirici reddi HTTP 200 doner, content bos olabilir."""
    yanit = _Yanit([], stop_reason="refusal", stop_details=_Ayrinti("cyber"))
    with pytest.raises(AjanHatasi) as e:
        agent._metni_al(yanit, "Ajan X")
    assert "reddedildi" in str(e.value)
    assert "cyber" in str(e.value)


def test_reddedilen_istek_kategorisiz_de_calisir():
    """stop_details None olabilir; denetim yine de patlamamali."""
    with pytest.raises(AjanHatasi):
        agent._metni_al(_Yanit([], stop_reason="refusal"), "Ajan X")


def test_kesik_yanit_ajanhatasi_firlatir():
    """Opus 5'te dusunme varsayilan acik ve max_tokens'i metinle paylasir.

    Kesik rapor bicim denetimini geciyor, ardindan raporu_linkleriyle_dogrula
    'Kaynaklar' bolumu ekleyip belgeyi tamamlanmis gosteriyordu.
    """
    yanit = _Yanit([_Blok("text", "Rapor yarida kal")], stop_reason="max_tokens")
    with pytest.raises(AjanHatasi) as e:
        agent._metni_al(yanit, "Ajan X")
    assert "max_tokens" in str(e.value)


def test_yalnizca_dusunme_blogu_ajanhatasi_firlatir():
    """display='omitted' oldugunda dusunme bloklarinin metni bostur.

    Eskiden varsayilansiz next() burada StopIteration firlatiyordu ve kullanici
    sebebi hic anlatmayan bir traceback goruyordu.
    """
    with pytest.raises(AjanHatasi) as e:
        agent._metni_al(_Yanit([_Blok("thinking", "")]), "Ajan X")
    assert "metin bloğu yok" in str(e.value)


def test_bos_metin_ajanhatasi_firlatir():
    with pytest.raises(AjanHatasi):
        agent._metni_al(_metin_yaniti("   \n "), "Ajan X")


def test_normal_yanit_metni_dondurur():
    assert agent._metni_al(_metin_yaniti("merhaba"), "Ajan X") == "merhaba"


def test_dusunme_blogu_metni_engellemez():
    """Normal calismada content dusunme + metin bloklarini birlikte tasir."""
    yanit = _Yanit([_Blok("thinking", ""), _Blok("text", "sonuc")])
    assert agent._metni_al(yanit, "Ajan X") == "sonuc"


def test_bozuk_json_ajanhatasi_firlatir(sahte_cagri):
    sahte_cagri(_metin_yaniti('{"secimler": ['))
    with pytest.raises(AjanHatasi) as e:
        agent._yapilandirilmis_cagri("s", "k", {}, ajan="Ajan X")
    assert "JSON" in str(e.value)


# ============================================================
# Ajan 1 — numara cozumleme
# ============================================================
def test_ajan1_numaralari_aday_kayitlarina_cozer(sahte_cagri, adaylar):
    sahte_cagri(_secim_yaniti([2, 0]))
    assert agent.baslik_okuyucu_ajani(adaylar, adet=12) == [
        {"baslik": "Haber 2", "link": "https://ornek.com/h2/"},
        {"baslik": "Haber 0", "link": "https://ornek.com/h0/"},
    ]


def test_ajan1_yinelenen_numarayi_eler(sahte_cagri, adaylar):
    """Ayni haber iki kez secilirse rapordaki 5 slottan ikisini yerdi."""
    sahte_cagri(_secim_yaniti([1, 1, 3]))
    linkler = [s["link"] for s in agent.baslik_okuyucu_ajani(adaylar, adet=12)]
    assert linkler == ["https://ornek.com/h1/", "https://ornek.com/h3/"]


def test_ajan1_aralik_disi_numarayi_eler(sahte_cagri, adaylar):
    sahte_cagri(_secim_yaniti([99, -1, 2]))
    linkler = [s["link"] for s in agent.baslik_okuyucu_ajani(adaylar, adet=12)]
    assert linkler == ["https://ornek.com/h2/"]


def test_ajan1_adet_sinirini_uygular(sahte_cagri, adaylar):
    sahte_cagri(_secim_yaniti([0, 1, 2, 3, 4, 5]))
    assert len(agent.baslik_okuyucu_ajani(adaylar, adet=3)) == 3


def test_ajan1_modele_hic_link_gondermez(sahte_cagri, adaylar):
    """Model URL kopyalamiyor; kayit tamamen bizim listemizden geliyor.

    Eskiden her URL'nin harfi harfine geri yazilmasi isteniyordu; modelin bir
    URL'yi normalize etmesi o secimin main.py'de sessizce elenmesine yol
    aciyordu.
    """
    kayit = sahte_cagri(_secim_yaniti([0]))
    agent.baslik_okuyucu_ajani(adaylar, adet=12)
    assert "https://" not in kayit["messages"][0]["content"]


# ============================================================
# Model ve effort sozlesmeleri
# ============================================================
def test_ajan1_dusuk_effort_ile_cagrilir(sahte_cagri, adaylar):
    """Mekanik ayiklama isi; varsayilan 'high' bosa token ve gecikme uretiyordu."""
    kayit = sahte_cagri(_secim_yaniti([0]))
    agent.baslik_okuyucu_ajani(adaylar, adet=12)
    assert kayit["model"] == agent.MODEL
    assert kayit["output_config"]["effort"] == "low"


def test_ajan2_haikuya_effort_gondermez(sahte_cagri):
    """Haiku 4.5 effort parametresini KABUL ETMEZ; gonderilirse 400 doner."""
    kayit = sahte_cagri(_metin_yaniti(
        json.dumps({"ai_ile_ilgili": True, "aciklama": "test"})))
    agent.icerik_inceleyici_ajani("baslik", "govde")
    assert kayit["model"] == agent.MODEL_UCUZ
    assert "effort" not in kayit["output_config"]


def test_ajan3_bol_butce_ile_cagrilir(sahte_cagri):
    """2048 ile rapor haberlerin ortasinda kesilebiliyordu."""
    kayit = sahte_cagri(_metin_yaniti("# Rapor"))
    agent.rapor_hazirlayici_ajani([])
    assert kayit["max_tokens"] >= 8192
    # Ajan 3 serbest metin yazar; sema gonderilmemeli.
    assert "format" not in kayit.get("output_config", {})


# ============================================================
# Prompt sozlesmeleri — prompt degisikligi kod degisikligidir
# ============================================================
def test_ajan3_promptu_gercek_alan_adini_kullanir(sahte_cagri):
    """Gonderilen sozlukte 'gerekce' diye bir alan yok; anahtar 'aciklama'.

    Siniflandirmayi tartismayi yasaklayan koruma var olmayan bir anahtara
    demirlendiginde yarim tutuyordu.
    """
    kayit = sahte_cagri(_metin_yaniti("# Rapor"))
    agent.rapor_hazirlayici_ajani([{"baslik": "b", "link": "https://ornek.com/a/",
                                    "tarih": "", "ai_ile_ilgili": True,
                                    "aciklama": "a"}])
    assert "'aciklama'" in kayit["system"]
    assert "gerekçe" not in kayit["system"]


def test_ajan1_kazinmis_veriyi_sinirlayici_icinde_gonderir(sahte_cagri, adaylar):
    kayit = sahte_cagri(_secim_yaniti([0]))
    agent.baslik_okuyucu_ajani(adaylar, adet=12)
    assert "<adaylar>" in kayit["messages"][0]["content"]
    assert agent._VERI_UYARISI in kayit["system"]


def test_ajan2_govdeyi_sinirlayici_icinde_gonderir(sahte_cagri):
    kayit = sahte_cagri(_metin_yaniti(
        json.dumps({"ai_ile_ilgili": False, "aciklama": "x"})))
    agent.icerik_inceleyici_ajani("bas", "govde metni")
    icerik = kayit["messages"][0]["content"]
    assert "<govde>" in icerik
    assert "govde metni" in icerik
    assert agent._VERI_UYARISI in kayit["system"]


def test_ajan3_analiz_sonuclarini_sinirlayici_icinde_gonderir(sahte_cagri):
    kayit = sahte_cagri(_metin_yaniti("# Rapor"))
    agent.rapor_hazirlayici_ajani([])
    assert "<analiz_sonuclari>" in kayit["messages"][0]["content"]
    assert agent._VERI_UYARISI in kayit["system"]
