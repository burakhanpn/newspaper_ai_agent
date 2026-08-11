"""
Gunluk raporun o gun basariyla uretilip gonderildigini denetler.

gunluk_rapor.log ve rapor.md'ye bakip tek satirlik bir durum verir. Hem elle
calistirmak icin, hem de Cowork nobetci gorevinin okumasi icin tasarlandi:
cikti hem insan tarafindan okunabilir, hem --json ile makine tarafindan.

Kullanim:
    python log_kontrol.py
    python log_kontrol.py --json
    python log_kontrol.py --gun 2026-08-11    # belirli bir gunu denetle

Cikis kodlari:
    0 = o gunku calisma basarili
    1 = calisma basarisiz (hata var)
    2 = o gun hic calisma kaydi yok
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")

KLASOR = Path(__file__).resolve().parent
LOG = KLASOR / "gunluk_rapor.log"
RAPOR = KLASOR / "rapor.md"

# .bat su bicimde yazar: [Sal 11.08.2026 10:30:01,90] === Calisma basladi ===
# Gun adi degisken oldugu icin sadece tarihi yakaliyoruz.
TARIH_DESENI = re.compile(r"\[\D*(\d{2})\.(\d{2})\.(\d{4})")

BASLANGIC = "=== Calisma basladi ==="
BITIS = "=== Tamamlandi ==="


def _log_satirlari() -> list[str]:
    if not LOG.exists():
        return []
    # Log cp1254 ya da utf-8 olabilir (duzeltme oncesi satirlar cp1254).
    for kodlama in ("utf-8", "cp1254", "latin-1"):
        try:
            return LOG.read_text(encoding=kodlama).splitlines()
        except UnicodeDecodeError:
            continue
    return LOG.read_text(encoding="utf-8", errors="replace").splitlines()


def _gunun_bloklari(satirlar: list[str], hedef: date) -> list[list[str]]:
    """Hedef gune ait '=== Calisma basladi ===' bloklarini dondurur."""
    bloklar, aktif, aktif_gun = [], None, None

    for satir in satirlar:
        eslesme = TARIH_DESENI.search(satir)
        if eslesme and BASLANGIC in satir:
            if aktif is not None and aktif_gun == hedef:
                bloklar.append(aktif)
            gun, ay, yil = (int(x) for x in eslesme.groups())
            aktif_gun = date(yil, ay, gun)
            aktif = [satir]
        elif aktif is not None:
            aktif.append(satir)

    if aktif is not None and aktif_gun == hedef:
        bloklar.append(aktif)
    return bloklar


def denetle(hedef: date) -> dict:
    satirlar = _log_satirlari()
    bloklar = _gunun_bloklari(satirlar, hedef)

    rapor_tarihi = (
        datetime.fromtimestamp(RAPOR.stat().st_mtime) if RAPOR.exists() else None
    )
    rapor_bugun = rapor_tarihi is not None and rapor_tarihi.date() == hedef

    if not bloklar:
        return {
            "durum": "CALISMADI",
            "mesaj": f"{hedef:%d.%m.%Y} icin log'da hic calisma kaydi yok. "
                     "Zamanlanmis gorev tetiklenmemis olabilir.",
            "rapor_guncel": rapor_bugun,
            "kod": 2,
        }

    son = bloklar[-1]
    metin = "\n".join(son)

    if BITIS in metin:
        return {
            "durum": "BASARILI",
            "mesaj": f"{hedef:%d.%m.%Y} raporu uretildi ve e-posta gonderildi.",
            "rapor_guncel": rapor_bugun,
            "kod": 0,
        }

    # Basarisiz: sebebi mumkun oldugunca daraltalim.
    hata_satiri = next(
        (s.strip() for s in reversed(son) if "HATA" in s or "Error" in s), ""
    )
    istisna = next(
        (s.strip() for s in reversed(son) if re.match(r"^\w+Error:", s.strip())), ""
    )
    yeni_yok = "Yeni haber yok" in metin

    if yeni_yok:
        return {
            "durum": "YENI_HABER_YOK",
            "mesaj": f"{hedef:%d.%m.%Y}: yeni haber bulunamadi, rapor "
                     "guncellenmedi ve e-posta gonderilmedi. Bu bir hata degil.",
            "rapor_guncel": rapor_bugun,
            "kod": 0,
        }

    return {
        "durum": "BASARISIZ",
        "mesaj": f"{hedef:%d.%m.%Y} calismasi tamamlanamadi.",
        "hata": istisna or hata_satiri or "(log'da acik bir hata satiri yok)",
        "rapor_guncel": rapor_bugun,
        "kod": 1,
    }


def main():
    ayristirici = argparse.ArgumentParser()
    ayristirici.add_argument("--json", action="store_true", help="Makine okunur cikti")
    ayristirici.add_argument("--gun", help="YYYY-AA-GG bicaminde denetlenecek gun")
    args = ayristirici.parse_args()

    hedef = date.fromisoformat(args.gun) if args.gun else date.today()
    sonuc = denetle(hedef)

    if args.json:
        print(json.dumps(sonuc, ensure_ascii=False, indent=2))
    else:
        simge = {"BASARILI": "OK", "BASARISIZ": "HATA",
                 "CALISMADI": "CALISMADI", "YENI_HABER_YOK": "BILGI"}[sonuc["durum"]]
        print(f"[{simge}] {sonuc['mesaj']}")
        if sonuc.get("hata"):
            print(f"       Sebep: {sonuc['hata']}")
        print(f"       rapor.md bugun guncellendi mi: "
              f"{'evet' if sonuc['rapor_guncel'] else 'HAYIR'}")

    sys.exit(sonuc["kod"])


if __name__ == "__main__":
    main()
