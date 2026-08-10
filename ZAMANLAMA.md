# Günlük Otomatik Çalıştırma Kurulumu (Windows Task Scheduler)

Bu proje internet erişimi (kaynak sitenin RSS akışı + makale sayfaları) gerektirdiği için
bulut/sandbox ortamlarında zamanlanamıyor; Windows Task Scheduler ile
**kendi bilgisayarınızda** her sabah 09:00'da otomatik çalıştırılması önerilir.

## 1. E-posta gönderimini ayarlayın

`send_report.py`, `rapor.md` dosyasını Gmail SMTP üzerinden gönderir.

1. Google hesabınızda [2 Adımlı Doğrulama](https://myaccount.google.com/security) açık olmalı.
2. [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) adresinden bir **Uygulama Şifresi** oluşturun.
3. `.env` dosyanıza şu satırları ekleyin:

   ```
   GMAIL_ADDRESS=sizin_adresiniz@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   RAPOR_ALICI=alici@ornek.com
   ```

4. Test edin:
   ```bash
   python send_report.py
   ```

## 2. Task Scheduler görevini oluşturun

1. Başlat menüsünden **Görev Zamanlayıcı (Task Scheduler)**'ı açın.
2. Sağ panelden **Temel Görev Oluştur...** (Create Basic Task) seçin.
3. Ad: `AI Haber Raporu`, isterseniz açıklama ekleyin → İleri.
4. Tetikleyici: **Günlük (Daily)** → İleri.
5. Başlangıç saati: **09:00:00**, her **1 gün**de bir → İleri.
6. Eylem: **Bir program başlat (Start a program)** → İleri.
7. Program/script alanına bu klasördeki **`gunluk_rapor_calistir.bat`** dosyasının
   tam yolunu yazın (örn. tam yol için dosyayı sağ tık → Kopyala, sonra buraya yapıştırın).
8. "Başlangıç konumu (Start in)" alanına projenin bulunduğu klasörün yolunu girin
   (bu `.bat` dosyasının olduğu klasör).
9. **Son (Finish)**.

### İsteğe bağlı ama önerilen ayarlar

Oluşturduğunuz görevi bulup **Özellikler (Properties)**'e girin:

- **Genel** sekmesi → "Kullanıcı oturum açmamış olsa bile çalıştır" seçilirse,
  bilgisayar kilitliyken de çalışır (Windows şifrenizi tekrar girmeniz istenir).
- **Koşullar** sekmesi → "Yalnızca AC gücündeyken başlat" kutusunun işaretini
  kaldırın (laptop kullanıyorsanız, pilde de çalışsın diye).
- **Ayarlar** sekmesi → "Görev başarısız olursa yeniden başlat" işaretleyip
  aralığı 10 dakika, deneme sayısını 2 yapabilirsiniz (RSS geçici olarak
  erişilemez olursa tekrar dener).

## 3. Doğrulama

Görevi sağ tıklayıp **Çalıştır (Run)** ile hemen tetikleyin, ardından
klasördeki `gunluk_rapor.log` dosyasını açıp hata olup olmadığını kontrol edin.

## Notlar

- `main.py` başarısız olursa (`.bat` dosyası içinde kontrol edilir) e-posta
  gönderilmez, böylece eski/boş rapor tekrar tekrar gönderilmez.
- Bilgisayar 09:00'da kapalıysa Windows görevi atlar (varsayılan davranış);
  "Kaçırılan görevi başlangıçta çalıştır" seçeneğini görev özelliklerinden
  açabilirsiniz.
