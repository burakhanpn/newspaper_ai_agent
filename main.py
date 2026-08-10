import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv
from tools import haber_adaylarini_getir, haber_icerigini_getir
from agent import (
    baslik_okuyucu_ajani,
    icerik_inceleyici_ajani,
    rapor_hazirlayici_ajani,
)

# .env dosyasındaki ortam değişkenlerini sisteme yükler
load_dotenv()

HEDEF_URL = "https://www.wired.com/"
KAYNAK_ADI = "The Verge"
# Bundan eski yazılar hiç değerlendirmeye alınmaz. Gün içinde çalıştırırken
# 24, hafta sonu boşluklarını da yakalamak için 48 makul.
TAZELIK_SAAT = 48


def _bir_haberi_isle(haber: dict) -> dict:
    """Tek bir haberi işler: içeriğini çeker ve İçerik İnceleyici Ajanı ile sınıflandırır.
    ThreadPoolExecutor tarafından paralel çağrılır."""
    icerik = haber_icerigini_getir(haber["link"])
    karar = icerik_inceleyici_ajani(haber["baslik"], icerik)
    print(f"      ✓ [{haber['tarih']}] {haber['baslik'][:55]}")
    return {
        "baslik": haber["baslik"],
        "link": haber["link"],
        "tarih": haber["tarih"],
        "ai_ile_ilgili": karar["ai_ile_ilgili"],
        "aciklama": karar["aciklama"],
    }


def main():
    # API anahtarının kontrolü
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY").startswith("sk-ant-sizin"):
        print("HATA: Lütfen .env dosyasını oluşturup geçerli bir ANTHROPIC_API_KEY değeri girin.")
        return

    print("--- Çok-Ajanlı Haber Analizi Başlatılıyor ---\n")

    # 0. Ham aday başlık+link+tarihleri RSS'ten çek
    print(f"[1/4] RSS akışı taranıyor (son {TAZELIK_SAAT} saat)...")
    try:
        adaylar = haber_adaylarini_getir(HEDEF_URL, max_saat=TAZELIK_SAAT)
    except Exception as e:
        print(f"HATA: RSS akışına erişilemedi: {e}")
        return
    if not adaylar:
        print(f"HATA: Son {TAZELIK_SAAT} saatte hiç haber adayı bulunamadı. "
              "RSS adresi veya akışın yapısı değişmiş olabilir.")
        return
    print(f"      {len(adaylar)} aday bulundu (en yenisi: {adaylar[0]['tarih']})")

    # 1. Ajan 1 — gerçek haberleri seç
    print("[2/4] Başlık Okuyucu Ajanı gerçek haberleri seçiyor...")
    secilenler = baslik_okuyucu_ajani(adaylar, adet=5)

    # Ajanın döndürdüğü link/tarihe güvenmiyoruz: link üzerinden asıl aday
    # kaydını buluyoruz. Böylece rapordaki tarih her zaman RSS'ten gelir ve
    # uydurulmuş ya da bozulmuş bir link listeye giremez.
    aday_dizini = {a["link"]: a for a in adaylar}
    haberler = [aday_dizini[s["link"]] for s in secilenler if s["link"] in aday_dizini]
    if not haberler:
        print("HATA: Ajan hiç geçerli haber seçemedi.")
        return
    if len(haberler) < len(secilenler):
        print(f"      UYARI: {len(secilenler) - len(haberler)} seçim tanınmayan "
              "link taşıdığı için elendi.")

    # 2. Ajan 2 — her haberin içeriğini PARALEL incele
    # (içerik çekme + sınıflandırma I/O ağırlıklı olduğundan iş parçacıkları hızlandırır;
    #  executor.map sonuçları girdiyle aynı sırada döndürür)
    print(f"[3/4] İçerik İnceleyici Ajanı {len(haberler)} haberi paralel analiz ediyor...")
    with ThreadPoolExecutor(max_workers=min(5, len(haberler))) as executor:
        sonuclar = list(executor.map(_bir_haberi_isle, haberler))

    # 3. Ajan 3 — nihai raporu yaz
    print("\n[4/4] Rapor Hazırlayıcı Ajanı raporu yazıyor...\n")
    rapor = rapor_hazirlayici_ajani(sonuclar)

    print("=" * 60)
    print(" NİHAİ RAPOR")
    print("=" * 60)
    print(rapor)

    # 4. Raporu markdown dosyasına kaydet (arşivlenebilir çıktı)
    # Sıralama için ham datetime'ları kullan: "dd.mm.yyyy" metni ay sınırında yanlış sıralanır.
    sirali = sorted(haberler, key=lambda h: h["_yayin"])
    altbilgi = (
        f"\n\n---\n_Kaynak: {KAYNAK_ADI} RSS · Haber aralığı: {sirali[0]['tarih']} – "
        f"{sirali[-1]['tarih']} "
        f"(son {TAZELIK_SAAT} saat) · Oluşturulma: {datetime.now():%d.%m.%Y %H:%M}_\n"
    )
    with open("rapor.md", "w", encoding="utf-8") as f:
        f.write(rapor + altbilgi)
    print("\n📄 Rapor 'rapor.md' dosyasına kaydedildi.")


if __name__ == "__main__":
    main()
