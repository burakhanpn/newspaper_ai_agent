import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv
from tools import (
    haber_adaylarini_getir,
    haber_icerigini_getir,
    gecmisi_yukle,
    gecmise_ekle,
)
from agent import (
    baslik_okuyucu_ajani,
    icerik_inceleyici_ajani,
    rapor_hazirlayici_ajani,
)

# .env dosyasındaki ortam değişkenlerini sisteme yükler
load_dotenv()

HEDEF_URL = "https://techcrunch.com/"
KAYNAK_ADI = "TechCrunch"
# Ana sayfadan kaç haber raporlanacak. Tazelik penceresi yok: sayfada ne
# varsa, sitenin sıraladığı önem sırasıyla alınır.
HABER_ADEDI = 5


def _bir_haberi_isle(haber: dict) -> dict:
    """Tek bir haberi işler: içeriğini ve yayın tarihini çeker, ardından
    İçerik İnceleyici Ajanı ile sınıflandırır.
    ThreadPoolExecutor tarafından paralel çağrılır."""
    sonuc = haber_icerigini_getir(haber["link"])
    karar = icerik_inceleyici_ajani(haber["baslik"], sonuc["icerik"])
    # Tarih bulunamamış olabilir; bu bir hata değil, sadece bilgi eksikliğidir.
    etiket = f"[{sonuc['tarih']}] " if sonuc["tarih"] else ""
    print(f"      ✓ {etiket}{haber['baslik'][:55]}")
    return {
        "baslik": haber["baslik"],
        "link": haber["link"],
        "tarih": sonuc["tarih"],
        # Sıralama için ham datetime. Ajan 3'e gönderilmeden önce main() içinde
        # ayıklanır: hem JSON'a serileştirilemez, hem de ajanın işine yaramaz.
        "_yayin": sonuc["_yayin"],
        "ai_ile_ilgili": karar["ai_ile_ilgili"],
        "aciklama": karar["aciklama"],
    }


def main():
    # API anahtarının kontrolü
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY").startswith("sk-ant-sizin"):
        print("HATA: Lütfen .env dosyasını oluşturup geçerli bir ANTHROPIC_API_KEY değeri girin.")
        return

    print("--- Çok-Ajanlı Haber Analizi Başlatılıyor ---\n")

    # 0. Ana sayfadaki makale linklerini editoryal sırayla çek
    print("[1/4] Ana sayfa taranıyor...")
    try:
        adaylar = haber_adaylarini_getir(HEDEF_URL)
    except Exception as e:
        print(f"HATA: Ana sayfaya erişilemedi: {e}")
        return
    if not adaylar:
        print("HATA: Ana sayfada hiç makale linki bulunamadı. Sayfa yapısı "
              "değişmiş ya da içerik JavaScript ile yükleniyor olabilir.")
        return
    print(f"      {len(adaylar)} aday bulundu")

    # 0b. Daha önce raporlanmış haberleri ele (tekrar kontrolü).
    # Ajan 1'e gitmeden önce eliyoruz: hem token tasarrufu, hem de ajanın
    # seçebileceği havuz sadece yeni haberlerden oluşuyor.
    gecmis = gecmisi_yukle()
    yeni_adaylar = [a for a in adaylar if a["link"] not in gecmis]
    atlanan = len(adaylar) - len(yeni_adaylar)
    if atlanan:
        print(f"      {atlanan} haber daha önce raporlandığı için atlandı")
    if not yeni_adaylar:
        print("\nAna sayfadaki haberlerin tamamı daha önce raporlanmış. "
              "Yeni rapor üretilmedi.")
        return

    # 1. Ajan 1 — gerçek haberleri seç
    print("[2/4] Başlık Okuyucu Ajanı gerçek haberleri seçiyor...")
    secilenler = baslik_okuyucu_ajani(yeni_adaylar, adet=HABER_ADEDI)

    # Ajanın döndürdüğü linke güvenmiyoruz: link üzerinden asıl aday kaydını
    # buluyoruz. Böylece uydurulmuş ya da bozulmuş bir link listeye giremez.
    aday_dizini = {a["link"]: a for a in yeni_adaylar}
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

    # Ham datetime'ları ayır: Ajan 3'e JSON olarak gidemezler ve orada işe
    # yaramazlar. Sıralamayı bunlarla yapıyoruz.
    yayinlar = [s.pop("_yayin") for s in sonuclar]

    # 3. Ajan 3 — nihai raporu yaz
    print("\n[4/4] Rapor Hazırlayıcı Ajanı raporu yazıyor...\n")
    rapor = rapor_hazirlayici_ajani(sonuclar)

    print("=" * 60)
    print(" NİHAİ RAPOR")
    print("=" * 60)
    print(rapor)

    # 4. Raporu markdown dosyasına kaydet (arşivlenebilir çıktı).
    # Tarih aralığı sadece tarihi bilinen haberlerden hesaplanır; hiçbirinde
    # tarih yoksa alt bilgide bu bölüm hiç görünmez.
    # Sıralama ham datetime ile yapılır: "dd.mm.yyyy" METNİ ay ve yıl sınırında
    # yanlış sıralanır (01.08 < 31.07 gibi).
    gecerli = sorted(y for y in yayinlar if y is not None)
    aralik = (
        f" · Haber aralığı: {gecerli[0].astimezone():%d.%m.%Y %H:%M}"
        f" – {gecerli[-1].astimezone():%d.%m.%Y %H:%M}"
    ) if gecerli else ""
    altbilgi = (
        f"\n\n---\n_Kaynak: {KAYNAK_ADI} ana sayfa · İlk {HABER_ADEDI} haber"
        f"{aralik} · Oluşturulma: {datetime.now():%d.%m.%Y %H:%M}_\n"
    )
    with open("rapor.md", "w", encoding="utf-8") as f:
        f.write(rapor + altbilgi)
    print("\n📄 Rapor 'rapor.md' dosyasına kaydedildi.")

    # 5. Geçmişi rapor BAŞARIYLA yazıldıktan sonra güncelle. Önce yazsaydık,
    # araya giren bir hata haberleri "raporlandı" sayar ve bir daha hiç
    # görünmemelerine yol açardı.
    gecmise_ekle([h["link"] for h in haberler], gecmis)


if __name__ == "__main__":
    main()
