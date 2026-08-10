# AI Haber Ajanı

Bu proje, Claude API üzerine kurulmuş çok-ajanlı basit bir haber analiz aracıdır. TechCrunch'ın **ana sayfasındaki ilk 5 haberi** alır, bu haberlerin 'yapay zeka' ile ilgili olup olmadığını analiz eder ve sonucu `rapor.md` dosyasına yazar.

Kaynak ve haber adedi `main.py` içindeki `HEDEF_URL` ve `HABER_ADEDI` değerlerinden ayarlanır.

## Nasıl çalışır

| Aşama | Ne yapar |
|---|---|
| Aday toplama | Ana sayfadaki makale linklerini **editoryal sırayla** çeker (`tools.py`) |
| Tekrar kontrolü | Daha önce raporlanmış linkleri eler (`gorulen_haberler.json`) |
| Ajan 1 | Gerçek haberleri seçer; rehber, inceleme, podcast, reklam gibi öğeleri eler |
| Ajan 2 | Her haberin gövdesini paralel olarak indirip AI ile ilgili mi diye sınıflandırır |
| Ajan 3 | Sonuçları akıcı bir Türkçe rapora dönüştürür |

### Sıralama ve tarih hakkında

Ana sayfa **kronolojik değil editoryal** olarak dizilidir: en üstteki haber, sitenin o an en önemli gördüğü haberdir. Bu yüzden "son X saat" gibi bir tazelik penceresi yoktur.

Yayın tarihi ana sayfa HTML'inde bulunmaz; makale sayfasının `article:published_time` meta etiketinden okunur. Bu zaten içerik için indirilen sayfadır, yani ek ağ maliyeti yoktur. Tarih bulunamazsa alan boş kalır ve rapora tarih yazılmaz — bu bir hata değildir.

### Tekrar kontrolü

Raporlanan her link `gorulen_haberler.json` dosyasına kaydedilir ve 30 gün boyunca tekrar seçilmez. Böylece ana sayfa günlerce güncellenmese bile aynı haberler tekrar tekrar rapora girmez. Dosya `.gitignore` ile hariç tutulmuştur; silinirse tekrar kontrolü sıfırlanır, program yine çalışır.

## Kurulum Adımları

1. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

2. Ortam değişkenlerini ayarlayın:
   `.env.example` dosyasını `.env` olarak kopyalayın ve içine kendi Anthropic (Claude) API anahtarınızı yapıştırın. E-posta göndermek isterseniz Gmail bilgilerini de doldurun (bkz. `ZAMANLAMA.md`).

3. Projeyi çalıştırın:
   ```bash
   python main.py
   ```

4. Raporu e-posta ile göndermek için:
   ```bash
   python send_report.py
   ```

## Bakım notu

Ana sayfa scraping'i, RSS'e göre daha kırılgandır: site tasarımını değiştirdiğinde `tools.py` içindeki `MAKALE_DESENI` ve `DISLANAN_YOLLAR` değerlerinin gözden geçirilmesi gerekebilir. "Ana sayfada hiç makale linki bulunamadı" hatası genellikle bunun işaretidir.

**Kaynak değiştirirken bu iki değeri mutlaka kontrol edin.** Her sitenin URL yapısı farklıdır ve uyumsuzluk sessizce yanlış sonuç üretir — hata vermez, sadece haber olmayan sayfalar listeye sızar. Örnek: The Verge yazar sayfaları için `/authors`, TechCrunch ise `/author` kullanır; liste tekil hâli içermediğinde çok tireli yazar isimleri (`/author/mary-ann-azevedo/`) makale sanılıp aday listesine giriyordu.
