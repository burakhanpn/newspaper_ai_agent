# Mimari

## Akış

```mermaid
flowchart TD
    A[Ana sayfa HTML] --> B["<b>tools.py</b> — mekanik eleme<br/>URL deseni, dışlanan yollar,<br/>başlık uzunluğu, tekrar"]
    B -->|~25 aday| C["<b>Ajan 1</b> — Başlık Okuyucu<br/>haber olmayanları eler<br/>(rehber, podcast, reklam)"]
    C -->|ADAY_HAVUZU aday| D["Paralel indirme<br/>her adayın yayın tarihi + gövdesi"]
    D --> E["<b>Tarih sıralaması</b><br/>en yeni HABER_ADEDI haber"]
    E --> F["<b>Ajan 2</b> — İçerik İnceleyici<br/>AI ile ilgili mi?<br/>EVET/HAYIR ölçüt listesi"]
    F --> G["<b>Ajan 3</b> — Rapor Hazırlayıcı<br/>Türkçe rapor + kaynak linkleri"]
    G --> H["<b>Doğrulama</b><br/>biçim denetimi + link doğrulama"]
    H -->|geçerse| I[rapor.md]
    H -->|kalırsa| X["çıkış kodu 1<br/>rapor kaydedilmez"]
    I --> J["<b>send_report.py</b><br/>tazelik kontrolü → e-posta"]

    style E fill:#2d4a3e,stroke:#4a7c59,color:#fff
    style H fill:#2d4a3e,stroke:#4a7c59,color:#fff
    style X fill:#4a2d2d,stroke:#7c4a4a,color:#fff
```

Yeşil kutular **deterministik** adımlardır — LLM kullanılmaz. Kesin cevabı olan
işler (sıralama, doğrulama) ajana sorulmaz.

## Ajanların rolleri

| Ajan | Girdi | Çıktı | Neden LLM? |
|---|---|---|---|
| 1 — Başlık Okuyucu | Ham başlık + link adayları | Ayıklanmış aday havuzu | Ana sayfa HTML'i dağınık; "bu haber, bu reklam" ayrımı kural yazmakla bitmez |
| 2 — İçerik İnceleyici | Makale gövde metni | `{ai_ile_ilgili, aciklama}` | Başlığa değil içeriğe bakarak karar verir; ölçüt listesi verilir ama yorum gerekir |
| 3 — Rapor Hazırlayıcı | Sınıflandırma sonuçları | Türkçe rapor | Yapılandırılmış veriyi insana okunur anlatıya çevirir |

Ajan 2 ucuz ve hızlı model kullanır (`claude-haiku-4-5`) çünkü haber başına bir
kez çağrılır. Ajan 1 ve 3 daha güçlü modelle çalışır (`claude-opus-5`).

## Ajan çıktısına neden güvenilmez?

Her ajanın çıktısı deterministik kodla doğrulanır:

```mermaid
flowchart LR
    A1[Ajan 1 linkleri] --> V1{"aday_dizini'nde<br/>var mı?"}
    V1 -->|hayır| D1[elenir + uyarı]
    V1 -->|evet| OK1[kabul]

    A3[Ajan 3 raporu] --> V2{"biçim denetimi<br/>haber raporu mu?"}
    V2 -->|hayır| D2["çıkış kodu 1<br/>e-posta yok"]
    V2 -->|evet| V3{"linkler gerçek mi?"}
    V3 -->|eksik| D3[Kaynaklar bölümü eklenir]
    V3 -->|uydurma| D4[uyarı]
    V3 -->|tam| OK2[kabul]
```

Bu katmanların her biri gerçek bir hatadan sonra eklendi:

- **Link doğrulama** — Ajan 3 bazı haberleri linksiz bırakıyordu.
- **Biçim denetimi** — Ajan 3'ün promptu bozulduğunda haber raporu yerine
  sınıflandırma denetimi yazdı. Çıktı biçimsel olarak kusursuzdu: taze tarihli,
  doğru linkli, hatasız çalışan bir belge — ama yanlış belge. Çıkış kodları,
  tazelik kontrolü ve log nöbetçisi dahil hiçbir denetim yakalamadı, çünkü hepsi
  *"çalıştı mı"* sorusunu sorar, *"doğru şeyi mi yaptı"* sorusunu değil.

## Neden iki aşamalı seçim?

Ana sayfa kronolojik değil **editoryal** olarak dizilidir: öne çıkarılan, günler
öncesine ait bir haber listenin en üstünde durabilir. Yayın tarihi de ana sayfa
HTML'inde bulunmaz; yalnızca makale sayfasının `article:published_time` meta
etiketindedir.

Bu yüzden önce Ajan 1 haber olmayanları eler, sonra kalan havuzun **tamamının**
sayfası indirilip tarihe göre sıralanır. `ADAY_HAVUZU` bu maliyetin ayarıdır:
havuz genişledikçe sıralama isabetli olur, karşılığında daha çok sayfa indirilir.
Pahalı olan LLM çağrıları yalnızca sıralamayı kazanan haberler için yapılır.

## Zamanlanmış çalışma

```mermaid
flowchart LR
    T["Task Scheduler<br/>her gün 09:00"] --> B[gunluk_rapor_calistir.bat]
    B --> M[main.py]
    M -->|kod 0| S[send_report.py]
    M -->|kod 1| E1["e-posta yok<br/>.bat kod 1 döner"]
    M -->|kod 2| E2["yeni haber yok<br/>.bat kod 0 döner"]
    S -->|kod 0| OK["=== Tamamlandi ==="]
    S -->|kod 1| E3["e-posta gitmedi<br/>.bat kod 1 döner"]
    B -.-> L[gunluk_rapor.log]
    L --> W["log_kontrol.py<br/>nöbetçi"]
```

Çıkış kodları kritik: `main.py` hata durumunda düz `return` yapsaydı kod 0
dönerdi ve `.bat` bunu başarı sanıp **bir önceki günün raporunu** yeniden
e-postalardı.
