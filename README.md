# AI Haber Ajanı

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Claude API üzerine kurulmuş çok-ajanlı bir haber analiz aracı. Bir teknoloji
haber sitesinin ana sayfasından **en son yayınlanmış haberleri** alır, yapay
zeka ile ilgili olanları ayıklar ve Türkçe bir rapora dönüştürüp e-posta ile
gönderir. Her sabah otomatik çalışacak şekilde zamanlanabilir.

> **In English:** A multi-agent news pipeline built on the Claude API. It
> scrapes a tech news homepage, filters out non-articles, ranks candidates by
> actual publication date, classifies each story as AI-related or not against
> an explicit rule set, and produces a Turkish-language Markdown report that
> is emailed on a daily schedule. Three Claude agents handle filtering,
> classification, and writing; deterministic Python code validates every agent
> output before it is trusted.

## Örnek çıktı

```markdown
# HABER RAPORU

## 🤖 Yapay Zeka Gündemi

### OpenAI, 7 milyar dolarlık çalışan hisse satış turunu tamamladı
OpenAI'nin, çalışanlarının hisselerini nakde çevirmesine olanak tanıyan
7 milyar dolarlık tender offer işlemini tamamladığı bildirildi. İşlem, yapay
zeka sektörüne akan sermayenin büyüklüğünü gösteriyor. (11.08.2026 03:03)
[Habere git](https://example.com/...)

## 📌 Diğer Haberler
...

## Genel Değerlendirme
...
```

## Mimari

Ayrıntılı diyagramlar ve tasarım gerekçeleri: [`docs/mimari.md`](docs/mimari.md)

```
Ana sayfa HTML
      │
      ▼
 tools.py            mekanik eleme: URL deseni, dışlanan yollar, başlık uzunluğu
      │              → ~25 aday
      ▼
 Ajan 1 (Claude)     haber olmayanları ele (rehber, podcast, reklam)
      │              → ADAY_HAVUZU kadar aday
      ▼
 Paralel indirme     her adayın sayfasından yayın tarihi + gövde metni
      │
      ▼
 Tarih sıralaması    en yeni HABER_ADEDI haber seçilir   ← deterministik, LLM yok
      │
      ▼
 Ajan 2 (Claude)     her haber AI ile ilgili mi? (EVET/HAYIR ölçüt listesi)
      │
      ▼
 Ajan 3 (Claude)     Türkçe rapor yazar, her habere kaynak linki ekler
      │
      ▼
 Doğrulama           biçim denetimi + link doğrulama       ← deterministik, LLM yok
      │
      ▼
 rapor.md ──► send_report.py ──► e-posta
```

Kaynak ve haber adedi `main.py` içindeki `HEDEF_URL` ve `HABER_ADEDI`
değerlerinden ayarlanır.

## Tasarım yaklaşımı: ajan çıktısına güvenilmez

Projenin ana fikri, üç LLM ajanının çıktısının deterministik kodla
doğrulanmasıdır. Ajanlar yaratıcı ve akıcı metin üretmekte iyi, ama link
kopyalamak, tarih sıralamak ve biçim tutturmak gibi işlerde güvenilmez.

| Ajanın işi | Kodun doğruladığı |
|---|---|
| Ajan 1 haber seçer | Döndürdüğü linkler aday listesinde var mı (`aday_dizini`) |
| Ajan 2 sınıflandırır | Şema ile yapılandırılmış çıktı (Structured Outputs) |
| Ajan 3 rapor yazar | Linkler gerçek mi (`raporu_linkleriyle_dogrula`), çıktı haber raporu mu (`raporu_bicim_dogrula`) |

Sıralama gibi kesin cevabı olan işler ajana hiç sorulmaz; tarihe göre seçim
tamamen Python tarafında yapılır.

## Nasıl çalışır

| Aşama | Ne yapar |
|---|---|
| Aday toplama | Ana sayfadaki makale linklerini çeker (`tools.py`) |
| Ajan 1 | Haber olmayanları eler (rehber, inceleme, podcast, reklam); geriye `ADAY_HAVUZU` kadar aday bırakır |
| Tarih sıralaması | Havuzdaki **her adayın** sayfası paralel indirilir, yayın tarihine göre sıralanır, en yeni `HABER_ADEDI` tanesi seçilir |
| Ajan 2 | Seçilen haberleri paralel olarak AI ile ilgili mi diye sınıflandırır |
| Ajan 3 | Sonuçları akıcı bir Türkçe rapora dönüştürür, her habere kaynak linkini ekler |

### Neden iki aşamalı seçim var?

Ana sayfa **kronolojik değil editoryal** olarak dizilidir: öne çıkarılan, günler öncesine ait bir haber listenin en üstünde durabilir. Bu yüzden sayfa sırası "en yeni" için güvenilir bir ölçüt değildir.

Yayın tarihi ana sayfa HTML'inde de bulunmaz; yalnızca makale sayfasının `article:published_time` meta etiketinde vardır. Dolayısıyla tarihe göre seçim yapabilmek için önce havuzdaki adayların sayfalarına bakmak, sonra seçmek gerekiyor. Ajan 1 bu yüzden sıralama yapmaz — sadece haber olmayanları eler.

`ADAY_HAVUZU` bu maliyetin ayarıdır: havuz ne kadar genişse tarih sıralaması o kadar isabetli olur, karşılığında o kadar çok sayfa indirilir. Pahalı olan LLM çağrıları yalnızca sıralamayı kazanan haberler için yapılır.

Tarihi okunamayan adaylar sıralamada en sona alınır; tarihi bilinmeyen bir haberin "en yeni" olduğu iddia edilemez. Havuz yetersiz kalırsa yine de listeye girebilirler ve rapora tarihsiz yazılırlar — bu bir hata değildir.

### Geçmiş kaydı (`gorulen_haberler.json`)

Raporlanan linkler bu dosyaya kaydedilir ve 30 gün tutulur. **Bu kayıt filtreleme için kullanılmaz** — yalnızca hangi haberin ne zaman ilk kez raporlandığını izlemek içindir.

Eskiden bu liste bir tekrar filtresiydi: geçmişte olan linkler havuzdan elenirdi. Ancak bu, aynı gün ikinci kez çalıştırıldığında günün taze haberlerini "zaten görüldü" diye eleyip programı sayfanın derinlerindeki eski haberlere itiyordu — yani ikinci çalışma, birincinin ürettiği iyi raporun üzerine daha kötüsünü yazıyordu. Filtre bu yüzden kaldırıldı; artık her çalışma o anki en yeni haberleri raporlar.

Dosya `.gitignore` ile hariç tutulmuştur; silinirse yalnızca arşiv sıfırlanır, program davranışı değişmez.

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

## Dosyalar

| Dosya | İşlevi |
|---|---|
| `main.py` | Akışı yürütür; çıkış kodlarıyla başarı/hata bildirir |
| `agent.py` | Üç Claude ajanının tanımı ve promptları |
| `tools.py` | Scraping, tarih ayrıştırma, rapor doğrulama |
| `send_report.py` | Raporu Gmail SMTP ile gönderir; tazelik kontrolü yapar |
| `log_kontrol.py` | Günlük çalışmanın durumunu denetler (nöbetçi) |
| `gunluk_rapor_calistir.bat` | Zamanlanmış çalışma zinciri (Windows) |
| `gorevi_kur.ps1` | Task Scheduler görevini tek komutla kurar |
| `ZAMANLAMA.md` | Otomatik çalıştırma kurulum rehberi |
| `docs/mimari.md` | Mimari diyagramları ve tasarım gerekçeleri |
| `tests/` | 59 test; ağ ve API anahtarı gerektirmez |

## Testler

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Testler scraping, LLM çağrıları ve SMTP bağlantısını taklit eder — internet
erişimi ya da API anahtarı gerekmez. Kapsam: URL ayıklama kuralları, tarih
ayrıştırma, tarihe göre seçim, çıkış kodları, rapor biçim/link doğrulama,
tazelik kontrolü ve e-posta oluşturma.

## Çıkış kodları

`main.py` ve `send_report.py` zamanlanmış çalıştırma için anlamlı kod döndürür:

| Kod | Anlamı |
|---|---|
| `0` | Rapor üretildi (ve gönderildi) |
| `1` | Hata; rapor üretilemedi veya gönderilemedi |
| `2` | Yeni haber yok — hata değil, ama gönderilecek yeni rapor da yok |

`.bat` dosyası bu kodlara bakarak e-posta gönderip göndermeyeceğine karar
verir. Bu ayrım önemli: `main.py` başarısız olduğunda kod 0 dönseydi, zincir
bir önceki günün raporunu taze sanıp yeniden gönderirdi.

## Lisans

[MIT](LICENSE)
