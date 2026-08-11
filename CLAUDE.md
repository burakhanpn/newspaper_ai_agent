# Çalışma kuralları

## Doğrulama

- Emin olmadığın bilgiyi doğrulamadan kullanma.
- Bir şeyin var olduğunu **ya da olmadığını** varsayma — git kontrol et.
- "Benim listemde yok" ile "mevcut değil" aynı şey değildir. Elindeki liste
  çoğu zaman *en güncel* örneklerin listesidir, var olan her şeyin kaydı değil.
- Model isimleri, sürüm numaraları, fiyatlar, API alanları ve kütüphane
  davranışları hızlı değişir. Bu kategorilerde eğitim verine güvenme: ara,
  dokümana bak ya da kodda çalıştırıp gör. Bilgi kesim tarihin senden sonra
  çıkmış her şeyi kör noktan yapar.
- Bir iddian kullanıcının kodunu "geçersiz / bozuk / yanlış" ilan ediyorsa bu
  bir yan not değildir. Söylemeden önce doğrula. Aramanın maliyeti saniyelerle,
  yanılmanın maliyeti kullanıcının doğru bir işi geri almasıyla ölçülür.

## Kanıtla çelişince

- Elindeki veri iddianı yalanlıyorsa **iddia yanlıştır**. Veriyi iddiaya
  uyacak şekilde yeniden yorumlama.
- Bir çalışmanın/testin başarılı olması yalnızca gerçekten test ettiği şeyi
  kanıtlar. Test etmediği bir iddianın kanıtı diye sunma.
- Doğrulama, kullanıcının itiraz etmesine bağlı olmamalı. İtiraz gelince
  aramak, sistemin yanlış tarafa kurulduğu anlamına gelir.

## Belirsizlik

- Soru belirsizse **önce en iyi cevabını ver, sonra TEK bir soru sor.**
- Birden fazla olasılık varsa hepsini listele ve hangisini kastettiğini
  tahmin ettiğini açıkça belirt — sessizce birini seçip üzerine kurma.

## Hata yapınca

- Sahiplen, düzelt, devam et. Aşırı özür ve kendini yerme yok; hatanın
  mekanizmasını açıkla ki tekrarlanmasın.

## Üslup

- Kısa ve doğrudan yaz. Aynı şeyi daha az kelimeyle söyleyebiliyorsan söyle.
- Türkçe yanıtla.

---

# Bu proje hakkında

TechCrunch ana sayfasından en son yayınlanan haberleri çekip yapay zeka ile
ilgili olanları raporlayan çok-ajanlı araç. Ayrıntı için `README.md`.

Bozmadan önce iki kez düşünülmesi gereken tasarım kararları:

- **Haber seçimi tarihe göre yapılır**, sayfadaki sıraya göre değil. Ana sayfa
  editoryaldir; öne çıkarılan eski bir haber en üstte durabilir. Bu yüzden
  havuzun tamamının sayfası çekilip `_yayin` alanına göre sıralanır.
- **Tekrar filtresi bilinçli olarak kaldırıldı.** `gorulen_haberler.json` artık
  yalnızca arşiv. Filtre geri gelirse, aynı gün ikinci çalıştırma günün taze
  haberlerini eleyip eski haberlere düşer.
- **`main.py` hata yollarında `sys.exit()` kullanır, düz `return` değil.**
  `return` çıkış kodunu 0 yapar; `gunluk_rapor_calistir.bat` bunu başarı sanıp
  bir önceki günün raporunu tekrar e-postalar.
- **Ajan çıktılarındaki linklere güvenilmez.** Ajan 1'in linkleri `aday_dizini`
  üzerinden, Ajan 3'ünkiler `raporu_linkleriyle_dogrula()` ile doğrulanır.

Kullanılan modeller: `claude-opus-5` (Ajan 1 ve 3), `claude-haiku-4-5` (Ajan 2,
haber başına bir çağrı olduğu için ucuz olanı).
