"""Gecici ag hatalarina karsi yeniden deneme testleri.

Gercek vaka (12.08.2026 09:17): zamanlanmis gorev, bilgisayar acilir acilmaz
StartWhenAvailable telafisiyle calisti; Windows hazirdi ama DNS degildi ve
tek denemede pes edildigi icin o gun hic rapor uretilmedi.
"""
import requests
import pytest

import tools


@pytest.fixture(autouse=True)
def bekleme_yok(monkeypatch):
    """Testler gercek sureleri beklemesin."""
    monkeypatch.setattr(tools.time, "sleep", lambda s: None)


class _Yanit:
    text = "<html><body></body></html>"
    content = b"<html><body></body></html>"
    def raise_for_status(self): pass


def test_ilk_denemede_basarili_olursa_beklenmez(monkeypatch):
    cagri = {"n": 0}
    def sahte(*a, **k):
        cagri["n"] += 1
        return _Yanit()
    monkeypatch.setattr(tools.requests, "get", sahte)

    assert tools._dayanikli_get("https://ornek.com/") is not None
    assert cagri["n"] == 1


def test_gecici_dns_hatasi_sonrasi_toparlar(monkeypatch):
    """Acilistaki DNS gecikmesi senaryosu: ilk iki deneme duser, ucuncusu tutar."""
    cagri = {"n": 0}
    def sahte(*a, **k):
        cagri["n"] += 1
        if cagri["n"] < 3:
            raise requests.exceptions.ConnectionError("getaddrinfo failed")
        return _Yanit()
    monkeypatch.setattr(tools.requests, "get", sahte)

    assert tools._dayanikli_get("https://ornek.com/") is not None
    assert cagri["n"] == 3


def test_kalici_ag_hatasi_sonunda_yukselir(monkeypatch):
    """Ag gercekten yoksa sonsuza kadar denenmez; hata yukselir ve kod 1 doner."""
    def sahte(*a, **k):
        raise requests.exceptions.ConnectionError("getaddrinfo failed")
    monkeypatch.setattr(tools.requests, "get", sahte)

    with pytest.raises(requests.exceptions.ConnectionError):
        tools._dayanikli_get("https://ornek.com/")


def test_deneme_sayisi_sinirli(monkeypatch):
    cagri = {"n": 0}
    def sahte(*a, **k):
        cagri["n"] += 1
        raise requests.exceptions.ConnectionError("getaddrinfo failed")
    monkeypatch.setattr(tools.requests, "get", sahte)

    with pytest.raises(requests.exceptions.ConnectionError):
        tools._dayanikli_get("https://ornek.com/")
    assert cagri["n"] == len(tools.DENEME_BEKLEMELERI) + 1


def test_http_hatasi_yeniden_denenmez(monkeypatch):
    """403/404 gecici degildir; tekrar denemek yalnizca zaman kaybettirir."""
    cagri = {"n": 0}
    class Reddedildi(_Yanit):
        def raise_for_status(self):
            raise requests.exceptions.HTTPError("403 Forbidden")
    def sahte(*a, **k):
        cagri["n"] += 1
        return Reddedildi()
    monkeypatch.setattr(tools.requests, "get", sahte)

    yanit = tools._dayanikli_get("https://ornek.com/")
    with pytest.raises(requests.exceptions.HTTPError):
        yanit.raise_for_status()
    assert cagri["n"] == 1


def test_ana_sayfa_cekimi_dayanikli_get_kullanir(monkeypatch):
    """haber_adaylarini_getir gecici hatadan sonra calismaya devam etmeli."""
    html = ('<html><body>'
            '<a href="https://ornek.com/2026/08/12/yeterince-uzun-haber-basligi/">'
            'Yeterince uzun bir haber basligi burada</a></body></html>')

    class Sayfa(_Yanit):
        text = html
        content = html.encode()

    cagri = {"n": 0}
    def sahte(*a, **k):
        cagri["n"] += 1
        if cagri["n"] == 1:
            raise requests.exceptions.ConnectionError("getaddrinfo failed")
        return Sayfa()
    monkeypatch.setattr(tools.requests, "get", sahte)

    adaylar = tools.haber_adaylarini_getir("https://ornek.com/")
    assert len(adaylar) == 1
    assert cagri["n"] == 2
