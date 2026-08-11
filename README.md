# AI Haber Ajanı

Bu proje, Claude API üzerine kurulmuş çok-ajanlı basit bir haber analiz aracıdır. TechCrunch'ın ana sayfasından **en son yayınlanmış 5 haberi** alır, bu haberlerin 'yapay zeka' ile ilgili olup olmadığını analiz eder ve sonucu `rapor.md` dosyasına yazar.

Kaynak ve haber adedi `main.py` içindeki `HEDEF_URL` ve `HABER_ADEDI` değerlerinden ayarlanır.

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
