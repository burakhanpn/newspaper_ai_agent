# AI Haber Ajanı

Bu proje, Claude API üzerine kurulmuş çok-ajanlı basit bir haber analiz aracıdır. The Verge'ün RSS akışından **son 48 saatin** en yeni 5 haberini alır ve bu haberlerin 'yapay zeka' ile ilgili olup olmadığını analiz edip `rapor.md` dosyasına yazar.

Kaynak ve tazelik penceresi `main.py` içindeki `HEDEF_URL` ve `TAZELIK_SAAT` değerlerinden ayarlanır.

> Not: Ana sayfa scraping'i yerine RSS kullanılıyor. Ana sayfa editoryal olarak dizilidir ve HTML'inde yayın tarihi bulunmaz; bu yüzden seçilen haberlerin güncel olduğu garanti edilemiyordu.

## Kurulum Adımları

1. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

2. Ortam değişkenlerini ayarlayın:
   `.env.example` dosyasının adını `.env` olarak değiştirin ve içine kendi Anthropic (Claude) API anahtarınızı yapıştırın.

3. Projeyi çalıştırın:
   ```bash
   python main.py
   ```
