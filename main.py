import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv

# Çıktıyı UTF-8'e sabitle. Zorunlu: .bat dosyası çıktıyı log dosyasına
# yönlendirdiğinde Python, konsol kodlaması yerine SİSTEM YEREL kodlamasını
# (Türkçe Windows'ta cp1254) kullanır. Rapordaki emojiler ve buradaki "✓"
# cp1254'te bulunmadığı için program UnicodeEncodeError ile çöker — üstelik
# yalnızca zamanlanmış görevde, elle çalıştırırken değil.
# errors="replace": beklenmedik bir karakter yine de çökmeye yol açmasın.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")
from tools import (
    haber_adaylarini_getir,
    haber_icerigini_getir,
    raporu_linkleriyle_dogrula,
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

# ---- Çıkış kodları ----
# Zamanlanmış görev (gunluk_rapor_calistir.bat) bu kodlara bakarak e-postayı
# gönderip göndermeyeceğine karar verir. print("HATA: ...") + return yetmez:
# düz `return` çıkış kodunu 0 yapar ve .bat hatayı başarı sanıp BİR ÖNCEKİ
# GÜNÜN raporunu tekrar gönderir.
CIKIS_BASARILI = 0   # yeni rapor.md yazıldı, gönderilebilir
CIKIS_HATA = 1       # gerçek hata; rapor üretilemedi
CIKIS_YENI_YOK = 2   # hata değil, ama gönderilecek yeni rapor da yok
# Rapora kaç haber girecek.
HABER_ADEDI = 5

# Ajan 1'in ayıkladıktan sonra döndüreceği aday havuzunun büyüklüğü.
# Bu havuzun TAMAMININ sayfası çekilir (yayın tarihini öğrenmek için), sonra
# tarihe göre sıralanıp en yeni HABER_ADEDI tanesi rapora alınır.
# Havuz > HABER_ADEDI olmalı; aksi halde sıralayacak bir şey kalmaz.
ADAY_HAVUZU = 12


def _sayfayi_cek(haber: dict) -> dict:
    """Aday haberin sayfasını indirip içeriğini ve yayın tarihini ekler.

    Sınıflandırmadan AYRI tutuluyor: tarihe göre sıralama yapabilmek için
    havuzdaki her adayın tarihini seçimden ÖNCE bilmemiz gerekiyor. Pahalı olan
    LLM çağrısı ise sadece sıralamayı kazanan haberler için yapılır.
    ThreadPoolExecutor tarafından paralel çağrılır.
    """
    sonuc = haber_icerigini_getir(haber["link"])
    return {
        "baslik": haber["baslik"],
        "link": haber["link"],
        "icerik": sonuc["icerik"],
        "tarih": sonuc["tarih"],
        # Sıralama için ham datetime; biçimlendirilmiş metin ay/yıl sınırında
        # yanlış sıralanır. Ajan 3'e gönderilmeden önce ayıklanır.
        "_yayin": sonuc["_yayin"],
    }


def _siniflandir(haber: dict) -> dict:
    """İçeriği çekilmiş bir haberi İçerik İnceleyici Ajanı ile sınıflandırır."""
    karar = icerik_inceleyici_ajani(haber["baslik"], haber["icerik"])
    # Tarih bulunamamış olabilir; bu bir hata değil, sadece bilgi eksikliğidir.
    etiket = f"[{haber['tarih']}] " if haber["tarih"] else ""
    print(f"      ✓ {etiket}{haber['baslik'][:55]}")
    return {
        "baslik": haber["baslik"],
        "link": haber["link"],
        "tarih": haber["tarih"],
        "_yayin": haber["_yayin"],
        "ai_ile_ilgili": karar["ai_ile_ilgili"],
        "aciklama": karar["aciklama"],
    }


def main():
    # API anahtarının kontrolü
    if not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY").startswith("sk-ant-sizin"):
        print("HATA: Lütfen .env dosyasını oluşturup geçerli bir ANTHROPIC_API_KEY değeri girin.")
        sys.exit(CIKIS_HATA)

    print("--- Çok-Ajanlı Haber Analizi Başlatılıyor ---\n")

    # 0. Ana sayfadaki makale linklerini editoryal sırayla çek
    print("[1/5] Ana sayfa taranıyor...")
    try:
        adaylar = haber_adaylarini_getir(HEDEF_URL)
    except Exception as e:
        print(f"HATA: Ana sayfaya erişilemedi: {e}")
        sys.exit(CIKIS_HATA)
    if not adaylar:
        print("HATA: Ana sayfada hiç makale linki bulunamadı. Sayfa yapısı "
              "değişmiş ya da içerik JavaScript ile yükleniyor olabilir.")
        sys.exit(CIKIS_HATA)
    print(f"      {len(adaylar)} aday bulundu")

    # NOT: Daha önce raporlanmış haberler artık ELENMİYOR. Eskiden geçmişte
    # olan linkler havuzdan çıkarılıyordu; bu, aynı gün ikinci kez çalıştırıldığında
    # günün taze haberlerini "zaten görüldü" diye eleyip ajanı sayfanın
    # derinlerindeki günler öncesine ait haberlere itiyordu. Artık her çalışmada
    # o anki en yeni haberler raporlanır. Geçmiş dosyası yalnızca arşiv/izleme
    # amacıyla yazılmaya devam ediyor (bkz. main() sonu).

    # 1. Ajan 1 — haber olmayanları ele, tarih sıralamasına girecek havuzu oluştur
    print("[2/5] Başlık Okuyucu Ajanı haber olmayanları eliyor...")
    secilenler = baslik_okuyucu_ajani(adaylar, adet=ADAY_HAVUZU)

    # Ajanın döndürdüğü linke güvenmiyoruz: link üzerinden asıl aday kaydını
    # buluyoruz. Böylece uydurulmuş ya da bozulmuş bir link listeye giremez.
    aday_dizini = {a["link"]: a for a in adaylar}
    havuz = [aday_dizini[s["link"]] for s in secilenler if s["link"] in aday_dizini]
    if not havuz:
        print("HATA: Ajan hiç geçerli haber seçemedi.")
        sys.exit(CIKIS_HATA)
    if len(havuz) < len(secilenler):
        print(f"      UYARI: {len(secilenler) - len(havuz)} seçim tanınmayan "
              "link taşıdığı için elendi.")
    print(f"      {len(havuz)} haber adayı havuza alındı")

    # 2a. Havuzdaki her adayın sayfasını PARALEL çek (içerik + yayın tarihi).
    # Tarihler ana sayfa HTML'inde olmadığı için seçim yapmadan önce her adayın
    # sayfasına bakmak zorundayız. Ağ ağırlıklı iş olduğundan paralel yürütülür.
    print(f"[3/5] {len(havuz)} adayın yayın tarihi ve içeriği paralel çekiliyor...")
    with ThreadPoolExecutor(max_workers=min(8, len(havuz))) as executor:
        zenginler = list(executor.map(_sayfayi_cek, havuz))

    # 2b. EN YENİ HABERLERİ SEÇ.
    # Ana sayfadaki sıra editoryaldir; öne çıkarılan günler öncesine ait bir
    # haber listenin üstünde durabilir. Bu yüzden seçim sayfa sırasına göre
    # değil, gerçek yayın tarihine göre yapılır.
    tarihli = [h for h in zenginler if h["_yayin"] is not None]
    tarihsiz = [h for h in zenginler if h["_yayin"] is None]
    tarihli.sort(key=lambda h: h["_yayin"], reverse=True)
    # Tarihi okunamayanlar en sona: tarihi bilinmeyen bir haberin "en yeni"
    # olduğunu iddia edemeyiz. Havuz yetersiz kalırsa yine de doldururlar.
    haberler = (tarihli + tarihsiz)[:HABER_ADEDI]

    if tarihsiz:
        print(f"      NOT: {len(tarihsiz)} adayın yayın tarihi okunamadı, "
              "sıralamada en sona alındı.")
    if tarihli:
        print(f"      En yeni {len(haberler)} haber seçildi "
              f"(havuzun en yenisi: {tarihli[0]['tarih']})")

    # 2c. Ajan 2 — yalnızca SEÇİLEN haberleri sınıflandır.
    # Pahalı olan LLM çağrısı; havuzun tamamı için değil, rapora girecekler
    # için yapılır.
    print(f"[4/5] İçerik İnceleyici Ajanı {len(haberler)} haberi paralel analiz ediyor...")
    with ThreadPoolExecutor(max_workers=min(5, len(haberler))) as executor:
        sonuclar = list(executor.map(_siniflandir, haberler))

    # Ham datetime'ları ayır: Ajan 3'e JSON olarak gidemezler ve orada işe
    # yaramazlar. Alt bilgideki tarih aralığını bunlarla hesaplıyoruz.
    yayinlar = [s.pop("_yayin") for s in sonuclar]

    # 3. Ajan 3 — nihai raporu yaz
    print("\n[5/5] Rapor Hazırlayıcı Ajanı raporu yazıyor...\n")
    rapor = rapor_hazirlayici_ajani(sonuclar)

    # Ajanın yazdığı linkleri gerçek haber linkleriyle doğrula. Eksik kalan
    # haberler rapora "Kaynaklar" bölümü olarak eklenir.
    rapor, link_uyarilari = raporu_linkleriyle_dogrula(rapor, sonuclar)
    for uyari in link_uyarilari:
        print(f"      UYARI: {uyari}")

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
        f"\n\n---\n_Kaynak: {KAYNAK_ADI} ana sayfa · En yeni {HABER_ADEDI} haber"
        f" ({len(havuz)} aday arasından)"
        f"{aralik} · Oluşturulma: {datetime.now():%d.%m.%Y %H:%M}_\n"
    )
    with open("rapor.md", "w", encoding="utf-8") as f:
        f.write(rapor + altbilgi)
    print("\n📄 Rapor 'rapor.md' dosyasına kaydedildi.")

    # 5. Geçmiş kaydını güncelle — ARTIK FİLTRELEME İÇİN DEĞİL, yalnızca
    # arşiv/izleme amacıyla: hangi haberin ne zaman ilk kez raporlandığını
    # görebilmek için. Rapor BAŞARIYLA yazıldıktan sonra yazılır.
    # gecmisi_yukle() burada çağrılıyor çünkü mevcut kayıtları koruyup
    # 30 günden eskileri budaması gerekiyor; yoksa dosya her çalışmada
    # sadece o günün linkleriyle üzerine yazılırdı.
    gecmise_ekle([h["link"] for h in haberler], gecmisi_yukle())


if __name__ == "__main__":
    main()
