import json
import anthropic

MODEL = "claude-opus-5"
# Yüksek hacimli (her haber için 1 kez çağrılan) içerik sınıflandırması için
# daha ucuz ve hızlı bir model. Structured Outputs'u destekler.
MODEL_UCUZ = "claude-haiku-4-5"

# İstemciyi tembel (lazy) oluşturuyoruz: modül import edildiği anda değil, ilk
# çağrıda. Böylece main.py'deki load_dotenv() çalıştıktan SONRA kurulur ve
# ANTHROPIC_API_KEY ortam değişkeni okunabilir.
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _yapilandirilmis_cagri(system: str, kullanici: str, sema: dict,
                           max_tokens: int = 2048, model: str = MODEL) -> dict:
    """Structured Outputs ile tek bir Claude çağrısı yapıp doğrulanmış JSON döndürür."""
    response = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": kullanici}],
        output_config={"format": {"type": "json_schema", "schema": sema}},
    )
    metin = next(blok.text for blok in response.content if blok.type == "text")
    return json.loads(metin)


# ============================================================
# Ajan 1 — Başlık Okuyucu
# ============================================================
_BASLIK_SEMASI = {
    "type": "object",
    "properties": {
        "haberler": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "baslik": {"type": "string"},
                    "link": {"type": "string"},
                },
                "required": ["baslik", "link"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["haberler"],
    "additionalProperties": False,
}


def baslik_okuyucu_ajani(adaylar: list[dict], adet: int = 12) -> list[dict]:
    """Ham başlık+link adayları arasından GERÇEK haberleri ayıklar.

    Bu ajan artık SIRALAMA YAPMAZ, sadece FİLTRELER. Nihai seçim main.py'de
    gerçek yayın tarihine göre yapılıyor; ana sayfadaki sıra buna güvenilir bir
    ölçüt değildi (öne çıkarılan eski haberler listenin üstünde durabiliyor).
    Bu yüzden `adet`, rapora girecek haber sayısı değil, tarih sıralamasına
    gönderilecek ADAY HAVUZUNUN büyüklüğüdür.
    """
    system = (
        "Sen başarılı bir haber editörüsün. Sana bir haber sitesinin ANA SAYFASINDAN toplanmış "
        "başlık ve link ikilileri verilecek. Görevin yalnızca AYIKLAMA yapmak: "
        "aralarından GERÇEK haberleri seç, haber olmayanları ele. "
        "Haber sayılmayanlar: alışveriş rehberi ('en iyi X'), ürün incelemesi, "
        "kupon/indirim sayfası, canlı blog, podcast, video, etkinlik duyurusu, "
        "bülten kaydı ve reklam.\n\n"
        f"Elemeden geçen haberlerden EN FAZLA {adet} tanesini döndür. "
        "Sıralama YAPMA ve önem değerlendirmesi yapma — hangi haberin rapora "
        "gireceğine daha sonra yayın tarihine bakılarak karar verilecek.\n\n"
        "ÖNEMLİ: Bu, haber olmayan öğelerin elendiği SON aşamadır. Sonraki "
        "adımlar yalnızca yayın tarihine ve haberin yapay zeka ile ilgisine "
        "bakar; bir öğenin haber olup olmadığını bir daha sorgulamaz. Bu yüzden "
        "kararsız kaldığın öğeyi LİSTEDEN ÇIKAR. Şüpheli bir öğeyi listede "
        "bırakmak, birkaç haber eksik döndürmekten daha kötüdür — çünkü o öğe "
        "doğrudan nihai rapora girer.\n\n"
        "Linkleri aynen koru, değiştirme."
    )
    aday_metni = "\n".join(
        f"- {a['baslik']} | {a['link']}" for a in adaylar
    )
    sonuc = _yapilandirilmis_cagri(system, f"Adaylar:\n{aday_metni}", _BASLIK_SEMASI)
    return sonuc["haberler"][:adet]


# ============================================================
# Ajan 2 — İçerik İnceleyici
# ============================================================
_ICERIK_SEMASI = {
    "type": "object",
    "properties": {
        "ai_ile_ilgili": {"type": "boolean"},
        "aciklama": {"type": "string", "description": "Kararın kısa Türkçe gerekçesi"},
    },
    "required": ["ai_ile_ilgili", "aciklama"],
    "additionalProperties": False,
}


def icerik_inceleyici_ajani(baslik: str, icerik: str) -> dict:
    """Bir makalenin içeriğine bakarak yapay zeka ile ilgili olup olmadığını döndürür.

    Sınır, modelin her seferinde yeniden yorumlamasına bırakılmaz: EVET ve HAYIR
    maddeleri tek tek sayılır. Kararsız kalınan durumda HAYIR'a düşer, böylece
    "AI" etiketi bilgi taşımaya devam eder.
    """
    system = (
        "Sen çok yetenekli bir teknoloji analistisin. Sana bir haberin başlığı ve "
        "gövde metni verilecek. Bu haberin bir YAPAY ZEKA HABERİ olup olmadığına "
        "karar ver.\n\n"

        "EVET say (aşağıdakilerden birine oturuyorsa):\n"
        "1. Yapay zeka teknolojisinin kendisi: modeller, yetenekler, araştırma, "
        "kıyaslama sonuçları, güvenlik ve hizalama.\n"
        "2. Yapay zeka ürün ve uygulamaları: bir ürünün AI özelliği haberin konusuysa.\n"
        "3. Ana işi yapay zeka olan şirketlerin SERMAYE olayları: yatırım turu, "
        "satın alma, halka arz, değerleme, hisse işlemleri. Bu tür haberler "
        "sektöre akan sermayenin ölçüsünü verdiği için AI haberidir.\n"
        "4. Yapay zekaya ÖZGÜ hukuk ve düzenleme: AI yasaları, telif davaları, "
        "AI standartları veya AI ürünleri üzerine açılan davalar.\n"
        "5. Yapay zeka için kritik donanım ve altyapı: eğitim çipleri, veri merkezi "
        "kapasitesi, enerji — haber bunları AI talebiyle ilişkilendiriyorsa.\n\n"

        "HAYIR say:\n"
        "1. Yapay zeka yalnızca yan cümlede, arka planda ya da pazarlama etiketi "
        "olarak geçiyorsa.\n"
        "2. Şirketin AI şirketi olması TEK BAŞINA yeterli değildir. Haberin konusu "
        "o şirketin yapay zekayla ilgisi olmayan sıradan kurumsal meselesiyse "
        "(yönetim değişikliği, ofis, marka anlaşmazlığı, İK) HAYIR.\n"
        "3. Genel teknoloji ve tüketici haberleri: uygulama mağazaları, ödeme "
        "yöntemleri, telefon donanımı, platform politikaları.\n"
        "4. Kişilerin şirketten bağımsız faaliyetleri (siyasi bağış, kişisel yatırım).\n\n"

        "Yukarıdaki maddelerin hiçbirine NET oturmuyorsa HAYIR döndür.\n\n"

        "Gerekçeni kısa ve Türkçe yaz ve hangi maddeye dayandığını belirt "
        "(örnek: 'EVET-3: ana işi AI olan şirketin sermaye işlemi')."
    )
    kullanici = f"BAŞLIK: {baslik}\n\nİÇERİK:\n{icerik}"
    return _yapilandirilmis_cagri(system, kullanici, _ICERIK_SEMASI, max_tokens=1024, model=MODEL_UCUZ)


# ============================================================
# Ajan 3 — Rapor Hazırlayıcı
# ============================================================
def rapor_hazirlayici_ajani(siniflandirmalar: list[dict]) -> str:
    """Tüm sınıflandırma sonuçlarını akıcı bir Türkçe rapora dönüştürür (düz metin/Markdown)."""
    system = (
        "Sen çok yetenekli bir editörsün. Sana analiz edilmiş haberlerin listesi "
        "(başlık, link, yayın tarihi, yapay zeka ile ilgili mi, gerekçe) verilecek. "
        "Kısa, akıcı ve düzenli bir Türkçe HABER RAPORU yaz: önce yapay zeka ile "
        "ilgili haberleri öne çıkar, sonra diğerlerini ver, en sonunda kısa bir genel "
        "değerlendirme ekle. Markdown kullan.\n\n"

        "Sana verilen 'ai_ile_ilgili' ve 'gerekçe' alanları KARAR VERİLMİŞ girdilerdir. "
        "Onları sorgulama, doğrulama, denetleme; sınıflandırmanın doğru olup olmadığını "
        "TARTIŞMA. Senin işin haberleri okura anlatmak, etiketleri değerlendirmek değil. "
        "'Etiket doğru', 'madde 3 gereği' gibi ifadeler kullanma — bunlar iç mekanizma, "
        "okuru ilgilendirmez.\n\n"

        "KURALLAR:\n"
        "1. HER haberin sonuna kaynak linkini Markdown biçiminde ekle: "
        "[Habere git](LINK)\n"
        "2. Linkleri sana verildiği gibi KARAKTER KARAKTER kopyala. Kısaltma, düzeltme, "
        "tamamlama ya da tahmin yapma; listede olmayan bir link asla yazma.\n"
        "3. Hiçbir haberi linksiz bırakma — genel değerlendirme bölümü hariç, "
        "bahsettiğin her habere linki eşlik etmeli.\n"
        "4. Haberin yayın tarihi doluysa belirt; 'tarih' alanı BOŞ ise tarihe hiç değinme "
        "ve 'tarih bilinmiyor' gibi bir ifade de kullanma."
    )
    veri = json.dumps(siniflandirmalar, ensure_ascii=False, indent=2)
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": f"Analiz sonuçları:\n{veri}"}],
    )
    return next(blok.text for blok in response.content if blok.type == "text")
