import json
import anthropic

MODEL = "claude-opus-4-8"
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


def baslik_okuyucu_ajani(adaylar: list[dict], adet: int = 5) -> list[dict]:
    """Ham başlık+link adayları arasından GERÇEK haberleri seçip ilk `adet` tanesini
    döndürür. Adaylar ana sayfadaki editoryal sırayla gelir."""
    system = (
        "Sen bir haber editörüsün. Sana bir haber sitesinin ANA SAYFASINDAN toplanmış "
        "başlık ve link ikilileri verilecek. Liste, haberlerin sayfada göründüğü "
        "EDİTORYAL SIRAYLA gelir: en üstteki, sitenin o an en önemli gördüğü haberdir. "
        "Aralarından yalnızca GERÇEK haberleri seç; alışveriş rehberi ('en iyi X'), ürün "
        "incelemesi, kupon/indirim sayfası, canlı blog, podcast, video ve reklam gibi "
        f"haber olmayan öğeleri ele. Eleme sonrası kalanların İLK {adet} tanesini, yani "
        "listede en üstte kalanları, verilen linkleriyle birlikte döndür. Sırayı konu "
        "ilgi çekiciliğine göre DEĞİŞTİRME — sayfadaki sırayı aynen koru. "
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
    """Bir makalenin içeriğine bakarak yapay zeka ile ilgili olup olmadığını döndürür."""
    system = (
        "Sen bir teknoloji analistisin. Sana bir haberin başlığı ve gövde metni verilecek. "
        "Haberin ASIL KONUSU yapay zeka mı (AI, makine öğrenimi, derin öğrenme, LLM, üretken "
        "yapay zeka vb.), karar ver. Konunun yalnızca yan cümlede geçmesi yeterli değildir; "
        "haberin merkezinde olmalı. Gerekçeni kısa ve Türkçe yaz."
    )
    kullanici = f"BAŞLIK: {baslik}\n\nİÇERİK:\n{icerik}"
    return _yapilandirilmis_cagri(system, kullanici, _ICERIK_SEMASI, max_tokens=1024, model=MODEL_UCUZ)


# ============================================================
# Ajan 3 — Rapor Hazırlayıcı
# ============================================================
def rapor_hazirlayici_ajani(siniflandirmalar: list[dict]) -> str:
    """Tüm sınıflandırma sonuçlarını akıcı bir Türkçe rapora dönüştürür (düz metin/Markdown)."""
    system = (
        "Sen çok yetenekli bir editörsün. Sana analiz edilmiş haberlerin listesi (başlık, link, "
        "yayın tarihi, yapay zeka ile ilgili mi, gerekçe) verilecek. Kısa, akıcı ve düzenli bir "
        "Türkçe rapor yaz: önce yapay zeka ile ilgili haberleri öne çıkar, sonra kısa bir genel "
        "değerlendirme ekle. Haberin yayın tarihi doluysa belirt; 'tarih' alanı BOŞ ise tarihe "
        "hiç değinme ve 'tarih bilinmiyor' gibi bir ifade de kullanma. Markdown kullanabilirsin."
    )
    veri = json.dumps(siniflandirmalar, ensure_ascii=False, indent=2)
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": f"Analiz sonuçları:\n{veri}"}],
    )
    return next(blok.text for blok in response.content if blok.type == "text")
