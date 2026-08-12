"""send_report.py testleri: tazelik kontrolu ve e-posta olusturma.

SMTP baglantisi taklit edilir; testler ag erisimi ya da gercek Gmail
kimlik bilgisi gerektirmez.
"""
import os
import smtplib
from datetime import datetime, timedelta

import pytest

import send_report


@pytest.fixture
def rapor_dosyasi(tmp_path):
    yol = tmp_path / "rapor.md"
    yol.write_text("# Rapor\n\nBugunun haberleri burada.\n", encoding="utf-8")
    return yol


def _yaslandir(yol, saat):
    """Dosyanin degistirilme zamanini geriye alir."""
    zaman = (datetime.now() - timedelta(hours=saat)).timestamp()
    os.utime(yol, (zaman, zaman))


# ============================================================
# Tazelik kontrolu
# ============================================================
def test_taze_rapor_gecer(rapor_dosyasi):
    send_report._tazelik_kontrolu(rapor_dosyasi, zorla=False)  # istisna atmamali


def test_bayat_rapor_gondermeyi_engeller(rapor_dosyasi):
    """main.py raporu guncelleyemediyse dunku rapor gonderilmemeli."""
    _yaslandir(rapor_dosyasi, send_report.TAZELIK_SAAT + 1)
    with pytest.raises(SystemExit) as e:
        send_report._tazelik_kontrolu(rapor_dosyasi, zorla=False)
    assert e.value.code == 1


def test_zorla_bayrag_tazelik_kontrolunu_atlar(rapor_dosyasi):
    _yaslandir(rapor_dosyasi, send_report.TAZELIK_SAAT + 48)
    send_report._tazelik_kontrolu(rapor_dosyasi, zorla=True)  # istisna atmamali


def test_tam_sinirdaki_rapor_gecer(rapor_dosyasi):
    """Esik degerin kendisi bayat sayilmaz."""
    _yaslandir(rapor_dosyasi, send_report.TAZELIK_SAAT - 0.1)
    send_report._tazelik_kontrolu(rapor_dosyasi, zorla=False)


# ============================================================
# E-posta olusturma
# ============================================================
@pytest.fixture
def sahte_smtp(monkeypatch):
    """SMTP'yi taklit eder ve gonderilen mesaji yakalar."""
    yakalanan = {}

    class SahteSMTP:
        def __init__(self, host, port, timeout=None):
            yakalanan["sunucu"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): yakalanan["tls"] = True
        def login(self, k, s): yakalanan["kullanici"] = k
        def send_message(self, msg): yakalanan["mesaj"] = msg

    monkeypatch.setattr(send_report.smtplib, "SMTP", SahteSMTP)
    monkeypatch.setenv("GMAIL_ADDRESS", "gonderen@ornek.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "xxxx xxxx xxxx xxxx")
    monkeypatch.setenv("RAPOR_ALICI", "alici@ornek.com")
    return yakalanan


def test_eposta_dogru_alicilara_gider(rapor_dosyasi, sahte_smtp):
    send_report.raporu_gonder(str(rapor_dosyasi))
    msg = sahte_smtp["mesaj"]
    assert msg["From"] == "gonderen@ornek.com"
    assert msg["To"] == "alici@ornek.com"


def test_alici_bos_ise_gonderene_gider(rapor_dosyasi, sahte_smtp, monkeypatch):
    monkeypatch.delenv("RAPOR_ALICI")
    send_report.raporu_gonder(str(rapor_dosyasi))
    assert sahte_smtp["mesaj"]["To"] == "gonderen@ornek.com"


def test_rapor_hem_govdede_hem_ek_olarak_gonderilir(rapor_dosyasi, sahte_smtp):
    send_report.raporu_gonder(str(rapor_dosyasi))
    parcalar = [p.get_content_type() for p in sahte_smtp["mesaj"].walk()]
    assert "text/plain" in parcalar
    assert "text/markdown" in parcalar


def test_turkce_karakterler_korunur(rapor_dosyasi, sahte_smtp):
    rapor_dosyasi.write_text("# Rapor\n\nYapay zeka gündemi: şirket, ağırlık, İstanbul.\n",
                             encoding="utf-8")
    send_report.raporu_gonder(str(rapor_dosyasi))
    govde = sahte_smtp["mesaj"].get_body(preferencelist=("plain",)).get_content()
    assert "gündemi" in govde and "şirket" in govde


def test_starttls_kullanilir(rapor_dosyasi, sahte_smtp):
    """Kimlik bilgileri sifresiz kanaldan gitmemeli."""
    send_report.raporu_gonder(str(rapor_dosyasi))
    assert sahte_smtp.get("tls") is True


# ============================================================
# Hata yollari — hepsi kod 1 dondurmeli ki .bat fark etsin
# ============================================================
def test_olmayan_dosya_kod_bir_doner(tmp_path, sahte_smtp):
    with pytest.raises(SystemExit) as e:
        send_report.raporu_gonder(str(tmp_path / "yok.md"))
    assert e.value.code == 1


def test_kimlik_bilgisi_eksikse_kod_bir_doner(rapor_dosyasi, monkeypatch):
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setenv("GMAIL_ADDRESS", "gonderen@ornek.com")
    with pytest.raises(SystemExit) as e:
        send_report.raporu_gonder(str(rapor_dosyasi))
    assert e.value.code == 1


def test_kimlik_dogrulama_hatasi_kod_bir_doner(rapor_dosyasi, sahte_smtp, monkeypatch):
    class RededenSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): raise smtplib.SMTPAuthenticationError(535, b"reddedildi")
        def send_message(self, m): pass
    monkeypatch.setattr(send_report.smtplib, "SMTP", RededenSMTP)
    with pytest.raises(SystemExit) as e:
        send_report.raporu_gonder(str(rapor_dosyasi))
    assert e.value.code == 1


def test_kalici_ag_hatasi_kod_bir_doner(rapor_dosyasi, sahte_smtp, monkeypatch):
    """DNS cozulemedigi gercek bir vaka yasandi; ham traceback log'u okunmaz yapiyordu."""
    import socket

    monkeypatch.setattr(send_report.time, "sleep", lambda s: None)

    class AgsizSMTP:
        def __init__(self, *a, **k):
            raise socket.gaierror(11001, "getaddrinfo failed")
    monkeypatch.setattr(send_report.smtplib, "SMTP", AgsizSMTP)
    with pytest.raises(SystemExit) as e:
        send_report.raporu_gonder(str(rapor_dosyasi))
    assert e.value.code == 1


# ============================================================
# Gecici DNS hatasindan toparlanma
# ============================================================
def test_gecici_dns_hatasi_sonrasi_gonderim_basarili(rapor_dosyasi, sahte_smtp, monkeypatch):
    """Gercek vaka (12.08.2026): main.py techcrunch'i cozdu, 14 sn sonra
    smtp.gmail.com cozulemedi. Ana sayfanin gelmesi SMTP'nin calisacagini
    garanti etmiyor; her isim aramasi ayri risk altinda."""
    import socket
    monkeypatch.setattr(send_report.time, "sleep", lambda s: None)

    cagri = {"n": 0}
    gercek_smtp = send_report.smtplib.SMTP

    class BazenDusenSMTP:
        def __init__(self, *a, **k):
            cagri["n"] += 1
            if cagri["n"] < 3:
                raise socket.gaierror(11001, "getaddrinfo failed")
            self._ic = gercek_smtp(*a, **k)
        def __enter__(self): return self._ic.__enter__()
        def __exit__(self, *a): return self._ic.__exit__(*a)

    monkeypatch.setattr(send_report.smtplib, "SMTP", BazenDusenSMTP)
    send_report.raporu_gonder(str(rapor_dosyasi))   # SystemExit atmamali
    assert cagri["n"] == 3
    assert "mesaj" in sahte_smtp


def test_kimlik_hatasi_yeniden_denenmez(rapor_dosyasi, sahte_smtp, monkeypatch):
    """Yanlis Uygulama Sifresi kalici bir hatadir; tekrar denemek anlamsiz."""
    monkeypatch.setattr(send_report.time, "sleep", lambda s: None)
    cagri = {"n": 0}

    class RededenSMTP:
        def __init__(self, *a, **k): cagri["n"] += 1
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, *a): raise smtplib.SMTPAuthenticationError(535, b"reddedildi")
        def send_message(self, m): pass

    monkeypatch.setattr(send_report.smtplib, "SMTP", RededenSMTP)
    with pytest.raises(SystemExit):
        send_report.raporu_gonder(str(rapor_dosyasi))
    assert cagri["n"] == 1, "kimlik hatasi yeniden denenmemeli"
