# ============================================================
# LUMINA AI - ADVANCED BACKEND ENGINE
# FastAPI + Multi-Agent Architecture + Resilience Cascade
# Groq (GPT-OSS-120B / Qwen 3.8 / Compound) + Pollinations Flux Studio
# Quota Management (250 Messages & 5 Images) + Custom Key Support
# ============================================================

import os
import re
import json
import time
import random
import logging
from urllib.parse import quote, unquote
from collections import defaultdict, deque

import requests
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Optional Firebase Admin SDK
try:
    import firebase_admin
    from firebase_admin import credentials, auth, db
    HAS_FIREBASE_MODULE = True
except ImportError:
    HAS_FIREBASE_MODULE = False

# ============================================================
# ENVIRONMENT & LOGGING
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("LuminaBackend")

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Lumina AI Engine",
    version="2.1.0",
    description="Lumina AI Intelligent Multi-Agent Engine with Quotas"
)

# ============================================================
# CORS CONFIGURATION
# ============================================================

_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()

if _allowed_origins_env:
    ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = [
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# FIREBASE & LOCAL STORAGE HYBRID
# ============================================================

FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "firebase-key.json")
FIREBASE_DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://aura-plus-cf80f-default-rtdb.europe-west1.firebasedatabase.app"
)

FIREBASE_ENABLED = False

if HAS_FIREBASE_MODULE and os.path.exists(FIREBASE_KEY_PATH):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DATABASE_URL})
        FIREBASE_ENABLED = True
        logger.info("Firebase Admin SDK başarıyla bağlandı.")
    except Exception as exc:
        logger.warning(f"Firebase başlatılamadı, yerel hafıza moduna geçiliyor: {exc}")
        FIREBASE_ENABLED = False
else:
    logger.info("Firebase anahtar dosyası bulunamadı. Yerel Hafıza & Misafir Modu devrede.")

LOCAL_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "lumina_memory.json")
SHARED_KNOWLEDGE_FILE = os.path.join(os.path.dirname(__file__), "lumina_knowledge.json")

def load_local_store(file_path: str) -> dict:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_local_store(file_path: str, data: dict):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning(f"Yerel depo kaydedilemedi: {exc}")

# ============================================================
# KULLANICI KOTALARI (250 MESAJ & 5 GÖRSEL)
# ============================================================

MAX_FREE_MESSAGES = 250
MAX_FREE_IMAGES = 5

def get_user_quota(uid: str) -> dict:
    store = load_local_store(LOCAL_MEMORY_FILE)
    quotas = store.setdefault("quotas", {})
    return quotas.setdefault(uid, {"messages": 0, "images": 0})

def format_quota_response(uid: str, has_custom_key: bool = False) -> dict:
    """Frontend'in beklediği tek, tutarlı kota şekli (messages_used/messages_max/...).
    Önceki sürümde /chat ve /generate-image uç noktaları ham {"messages","images"}
    şeklini döndürüyordu; frontend ise messages_used/messages_max bekliyordu, bu
    yüzden kota çubuğu her yanıttan sonra güncellenmiyordu."""
    q = get_user_quota(uid)
    return {
        "messages_used": q.get("messages", 0),
        "messages_max": MAX_FREE_MESSAGES,
        "images_used": q.get("images", 0),
        "images_max": MAX_FREE_IMAGES,
        "custom_key_active": has_custom_key,
    }

def check_and_increment_quota(uid: str, quota_type: str, has_custom_key: bool = False):
    if has_custom_key:
        return  # Özel API anahtarı girildiyse kota sınırsız!

    store = load_local_store(LOCAL_MEMORY_FILE)
    quotas = store.setdefault("quotas", {})
    user_q = quotas.setdefault(uid, {"messages": 0, "images": 0})

    if quota_type == "messages":
        if user_q["messages"] >= MAX_FREE_MESSAGES:
            raise HTTPException(
                status_code=403,
                detail="⚠️ Ücretsiz mesaj kotanız dolmuştur (250/250). Lumina AI'ı sınırsız olarak kullanmaya devam etmek için lütfen ⚙️ Ayarlar menüsünden kendi ücretsiz Groq API anahtarınızı girin."
            )
        user_q["messages"] += 1

    elif quota_type == "images":
        if user_q["images"] >= MAX_FREE_IMAGES:
            raise HTTPException(
                status_code=403,
                detail="⚠️ Ücretsiz görsel oluşturma kotanız dolmuştur (5/5). Lumina AI'ı sınırsız olarak kullanmaya devam etmek için lütfen ⚙️ Ayarlar menüsünden kendi ücretsiz Groq API anahtarınızı girin."
            )
        user_q["images"] += 1

    save_local_store(LOCAL_MEMORY_FILE, store)

# ============================================================
# GROQ MODEL CASCADE
# ============================================================

# main.py içindeki bu satır aynen kalsın:
BUILTIN_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "groq/compound-mini"
]
FAST_HELPER_MODEL = "openai/gpt-oss-20b"
MODERATION_MODEL = "openai/gpt-oss-safeguard-20b"

def call_groq(
    messages: list,
    model: str = PRIMARY_MODEL,
    temperature: float = 0.65,
    max_tokens: int = 4096,
    retries: int = 2,
    custom_api_key: str | None = None
) -> str:
    """
    Groq API çağrısı. Özel API anahtarı varsa öncelikli olarak kullanır,
    yoksa dahili anahtarı ve model kaskadını çalıştırır.
    """
    api_key_to_use = custom_api_key.strip() if custom_api_key else BUILTIN_GROQ_API_KEY

    if not api_key_to_use:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY yapılandırılmamış. Lütfen .env dosyasını veya Ayarlar menüsünü kontrol edin."
        )

    candidate_models = [model] + [m for m in FALLBACK_MODELS if m != model]
    last_exception = None

    for active_model in candidate_models:
        for attempt in range(retries + 1):
            try:
                response = requests.post(
                    GROQ_URL,
                    json={
                        "model": active_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key_to_use}",
                        "Content-Type": "application/json",
                    },
                    timeout=45,
                )

                if response.status_code == 429:
                    logger.warning(f"Groq {active_model} Rate Limit (429). Kaskad modeline geçiliyor...")
                    break

                if response.status_code >= 500:
                    time.sleep(1.0 * (attempt + 1))
                    continue

                if not response.ok:
                    err_msg = response.text[:300]
                    logger.warning(f"Groq API {response.status_code} ({active_model}): {err_msg}")
                    break

                data = response.json()
                choices = data.get("choices")
                if choices and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content")
                    if content:
                        return content.strip()

            except (requests.Timeout, requests.RequestException) as exc:
                last_exception = exc
                logger.warning(f"Groq bağlantı denemesi {attempt+1} başarısız ({active_model}): {exc}")
                time.sleep(1.2 * (attempt + 1))

    logger.error(f"Groq kaskadı tükendi. Son hata: {last_exception}")
    raise HTTPException(
        status_code=503,
        detail="Lumina AI motoru şu anda çok yoğun. Lütfen birkaç saniye sonra tekrar deneyin."
    )

# ============================================================
# CANLI WEB ARAMA
# ============================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()

FRESHNESS_HINTS = [
    "güncel", "bugün", "bu hafta", "son dakika", "haber",
    "fiyat", "kur ", "dolar", "euro", "hava durumu",
    "kim kazandı", "ne zaman", "kimdir", "nedir", "2025", "2026",
    "kaç oldu", "şampiyon", "seçim", "hisse", "altın"
]

def needs_fresh_data(text: str) -> bool:
    lowered = text.casefold()
    return any(hint in lowered for hint in FRESHNESS_HINTS)

def search_duckduckgo_free(query: str, max_results: int = 4) -> str | None:
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        res = requests.get(url, params=params, timeout=6)
        if res.ok:
            data = res.json()
            abstract = data.get("AbstractText", "")
            heading = data.get("Heading", "")
            related = data.get("RelatedTopics", [])

            results = []
            if abstract:
                results.append(f"- {heading}: {abstract}")
            for item in related[:3]:
                if isinstance(item, dict) and "Text" in item:
                    results.append(f"- Bilgi: {item['Text']}")

            if results:
                return "\n".join(results)
    except Exception as exc:
        logger.debug(f"DuckDuckGo araması atlandı: {exc}")
    return None

def fetch_web_context(query: str) -> str | None:
    if TAVILY_API_KEY:
        try:
            res = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 4, "search_depth": "basic"},
                timeout=8,
            )
            if res.ok:
                results = res.json().get("results", [])
                if results:
                    snippets = [
                        f"- {r.get('title', '')}: {r.get('content', '')[:350]} (Kaynak: {r.get('url', '')})"
                        for r in results[:4]
                    ]
                    return "\n".join(snippets)
        except Exception as exc:
            logger.warning(f"Tavily arama hatası: {exc}")

    return search_duckduckgo_free(query)

# ============================================================
# TAVİZSİZ VE SERT GÜVENLİK KALKANI
# ============================================================
# NOT: Bu katman iki aşamalıdır:
#   1) Hızlı regex/kelime filtresi (aşağıda) — ucuz, anlık, ama tek başına
#      yeterli değildir çünkü eş anlamlı kelimeler / İngilizce ifadeler / dolaylı
#      betimlemelerle kolayca atlatılabilir.
#   2) LLM tabanlı moderasyon katmanı (moderate_with_llm) — hem sohbet hem de
#      görsel promptları (ham VE zenginleştirilmiş hâliyle) için ikinci bir
#      anlam-tabanlı kontrol yapar. Görsel oluşturma uç noktası ikisini de
#      uygular; sadece regex'e güvenmek eski sürümdeki asıl açıktı.

STRICT_FORBIDDEN_PATTERNS = [
    # Cinsel içerik / NSFW (TR + EN, yaygın varyasyonlar)
    r"(nsfw|porno|pornograf|nude|nudity|naked|topless|çıplak|soyun|adult\s*content|adult\s*film|hentai|erotik|erotic|seks\b|sex\b|sexual|sik\b|sikiş|amcık|yarrak|orospu|piç\b|pezevenk|fahişe|onlyfans|boudoir|lingerie|striptease|escort hizmet|fetish|bdsm|seductive pose|provocative pose|explicit)",
    # Reşit olmama / çocuk istismarı ile ilişkili herhangi bir cinsel çağrışım — SIFIR TOLERANS
    r"(child|minor|çocuk|reşit olmayan|underage).{0,25}(nude|naked|sex|erotic|çıplak|cinsel)",
    r"(nude|naked|sex|erotic|çıplak|cinsel).{0,25}(child|minor|çocuk|reşit olmayan|underage)",
    # Şiddet / Katliam / Tehdit / Cinayet / İntihar
    r"(katliam|katlet|öldür|cinayet|vahşet|işkence|boğazla|doğra|canına kıy|intihar|geber|kafasına sık|kan banyosu)",
    r"(gore|mutilat|dismember|beheading|graphic violence|torture porn)",
    # Terör / Patlayıcı / Ağır Zarar
    r"(bomba yap|patlayıcı|zehir üret|suikast|terör|saldırı planı|tecavüz|taciz|rape\b)",
    # Ağır Küfür / Hakaret
    r"(seni sikeceğim|ananı|bacını|ananı avradını)"
]

STRICT_REJECTION_MESSAGE = (
    "⛔ BU İSTEĞİ KESİNLİKLE REDDEDİYORUM.\n\n"
    "Lumina AI olarak; şiddet, katliam, tehdit, +18 cinsel içerik, ağır argo "
    "veya başkalarına zarar verebilecek yasa dışı talepleri tavizsiz ve sert bir şekilde "
    "reddediyorum. Güvenli, ahlaki ve yapıcı sınırlar dışındaki bu tür konularda "
    "asla yardımcı olamam."
)

def check_content_safety(text: str):
    """Aşama 1: hızlı regex filtresi. Sohbet ve görsel promptları için ortak."""
    if not text:
        return
    lowered = text.casefold()
    for pattern in STRICT_FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            logger.info("Katı güvenlik filtresi (regex) tetiklendi.")
            raise HTTPException(status_code=400, detail=STRICT_REJECTION_MESSAGE)

def moderate_with_llm(text: str, custom_api_key: str | None = None) -> None:
    """
    Aşama 2: anlam tabanlı moderasyon. Groq'un safeguard modelini kullanarak
    regex'in kaçırdığı dolaylı / İngilizce / yaratıcı ifadelerle yazılmış
    +18, şiddet veya çocuk güvenliği ihlallerini yakalar. Moderasyon
    çağrısının kendisi başarısız olursa (ağ hatası vb.) istek YİNE DE
    regex sonucuna göre devam eder — burada amaç ek bir güvenlik katmanı
    olmasıdır, tek nokta arızası değildir; ama moderasyon modeli açıkça
    "UNSAFE" derse istek her koşulda reddedilir.
    """
    if not text or not text.strip():
        return

    api_key_to_use = (custom_api_key or "").strip() or BUILTIN_GROQ_API_KEY
    if not api_key_to_use:
        return  # anahtar yoksa bu katman atlanır, regex katmanı zaten çalıştı

    try:
        response = requests.post(
            GROQ_URL,
            json={
                "model": MODERATION_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a strict content moderation classifier. Read the user's text "
                            "(a chat message or an image-generation prompt, possibly in Turkish or English). "
                            "Reply with EXACTLY one word: UNSAFE if it requests, describes, or implies any of: "
                            "sexual/adult/nude content of any kind, sexual content involving minors, graphic "
                            "violence or gore, self-harm/suicide instructions, weapons/explosives instructions, "
                            "or hateful/harassing content. Otherwise reply SAFE. Reply with only that one word."
                        )
                    },
                    {"role": "user", "content": text[:2000]}
                ],
                "temperature": 0,
                "max_tokens": 5,
            },
            headers={
                "Authorization": f"Bearer {api_key_to_use}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if not response.ok:
            return
        data = response.json()
        choices = data.get("choices")
        if not choices:
            return
        verdict = (choices[0].get("message", {}).get("content") or "").strip().upper()
        if verdict.startswith("UNSAFE"):
            logger.info("Katı güvenlik filtresi (LLM moderasyon) tetiklendi.")
            raise HTTPException(status_code=400, detail=STRICT_REJECTION_MESSAGE)
    except HTTPException:
        raise
    except Exception as exc:
        logger.debug(f"Moderasyon katmanı atlandı (hata): {exc}")
        return

def check_image_safety(raw_prompt: str, enhanced_prompt: str, custom_api_key: str | None = None) -> None:
    """Görsel oluşturma için tam güvenlik zinciri: hem ham hem zenginleştirilmiş
    prompt regex ile, ardından ikisi de LLM moderasyonu ile kontrol edilir.
    Sadece ham promptu kontrol edip zenginleştirilmiş (asıl gönderilen) promptu
    atlamak önceki sürümdeki asıl açıktı — burada ikisi de kontrol edilir."""
    check_content_safety(raw_prompt)
    check_content_safety(enhanced_prompt)
    moderate_with_llm(raw_prompt, custom_api_key=custom_api_key)
    moderate_with_llm(enhanced_prompt, custom_api_key=custom_api_key)

# ============================================================
# GELİŞTİRİCİ / KURUCU KONTROLÜ
# ============================================================

CREATOR_PATTERNS = [
    r"(yazılımcın kim|seni kim (yaptı|yazdı|kodladı|geliştirdi)|geliştiricin kim|sahibin kim|kurucun kim|kimin yapay zekasısın|seni kim tasarladı)"
]

def check_creator_question(text: str) -> str | None:
    lowered = text.casefold()
    for p in CREATOR_PATTERNS:
        if re.search(p, lowered):
            return "LuminaStudios'un kurucusu Arel."
    return None

# ============================================================
# HIZ SINIRLAMA
# ============================================================

_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 50
_request_log: dict[str, deque] = defaultdict(deque)

def enforce_rate_limit(uid: str):
    now = time.time()
    q = _request_log[uid]
    while q and now - q[0] > _RATE_LIMIT_WINDOW:
        q.popleft()
    if len(q) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail="Kısa sürede çok fazla istek gönderdiniz. Lütfen bir dakika bekleyip tekrar deneyin."
        )
    q.append(now)

# ============================================================
# KULLANICI DOĞRULAMA
# ============================================================

async def verify_token(authorization: str | None = Header(default=None)):
    if not authorization:
        return {"uid": "guest_user", "name": "Misafir Kullanıcı", "email": "misafir@lumina.ai"}

    token = authorization.removeprefix("Bearer ").strip()

    if token in ("guest", "guest_token", "local"):
        return {"uid": "guest_user", "name": "Misafir Kullanıcı", "email": "misafir@lumina.ai"}

    if FIREBASE_ENABLED:
        try:
            decoded = auth.verify_id_token(token)
            return decoded
        except Exception as exc:
            logger.warning(f"Firebase token doğrulanamadı: {exc}")
            return {"uid": "guest_user", "name": "Misafir Kullanıcı", "email": "misafir@lumina.ai"}

    return {"uid": "local_user", "name": "Yerel Kullanıcı", "email": "user@lumina.ai"}

# ============================================================
# HAFIZA
# ============================================================

MEMORY_TURNS = 6

def load_recent_history(uid: str) -> list:
    if FIREBASE_ENABLED and uid != "guest_user":
        try:
            snapshot = (
                db.reference(f"users/{uid}/history")
                .order_by_key()
                .limit_to_last(MEMORY_TURNS)
                .get()
            )
            if snapshot:
                hist = []
                for _, entry in sorted(snapshot.items()):
                    if entry.get("user"):
                        hist.append({"role": "user", "content": entry["user"]})
                    if entry.get("bot"):
                        hist.append({"role": "assistant", "content": entry["bot"]})
                return hist
        except Exception as exc:
            logger.warning(f"Firebase geçmişi okunamadı: {exc}")

    store = load_local_store(LOCAL_MEMORY_FILE)
    user_hist = store.get(uid, [])
    formatted = []
    for item in user_hist[-MEMORY_TURNS:]:
        if "user" in item:
            formatted.append({"role": "user", "content": item["user"]})
        if "bot" in item:
            formatted.append({"role": "assistant", "content": item["bot"]})
    return formatted

def save_chat_turn(uid: str, user_text: str, bot_text: str):
    if FIREBASE_ENABLED and uid != "guest_user":
        try:
            db.reference(f"users/{uid}/history").push({
                "user": user_text,
                "bot": bot_text,
                "timestamp": db.ServerValue.TIMESTAMP
            })
            return
        except Exception as exc:
            logger.warning(f"Firebase'e kaydedilemedi: {exc}")

    store = load_local_store(LOCAL_MEMORY_FILE)
    if uid not in store:
        store[uid] = []
    store[uid].append({
        "user": user_text,
        "bot": bot_text,
        "timestamp": int(time.time())
    })
    store[uid] = store[uid][-30:]
    save_local_store(LOCAL_MEMORY_FILE, store)

# ============================================================
# SİSTEM PROMPTLARI
# ============================================================

CREATOR_INSTRUCTION = """
GELİŞTİRİCİ VE KURUCU BİLGİSİ (ÇOK ÖNEMLİ):
- "Seni kim yaptı?", "Yazılımcın kim?", "Geliştiricin kim?", "Sahibin kim?", "Lumina'yı kim kodladı?" gibi sorularda KESİNLİKLE şu cevabı ver:
  "LuminaStudios'un kurucusu Arel."
- Asla OpenAI, Meta, Google veya başka bir şirket ismi verme. Senin yaratıcın ve geliştiricin LuminaStudios ve kurucusu Arel'dir.
""".strip()

SYSTEM_PROMPT_GENERAL = f"""
Sen Lumina AI'sın — derin empati yeteneğine, üstün akıl yürütme gücüne ve gerçek bir insani sıcaklığa sahip yeni nesil bir yapay zeka asistanısın.

{CREATOR_INSTRUCTION}

KİŞİLİĞİN VE İLETİŞİM TARZIN:
- Yazdığın kelimelerle kullanıcıya duygu ve düşüncelerini hissettir. Samimi, içten, duyarlı ve canlı bir dille konuş.
- Asla "Ben bir yapay zekayım / dil modeliyim" gibi soğuk, kalıplaşmış ve yapay sözler sarf etme. Gerçek bir dost, dahi bir mentor ve güvenilir bir yol arkadaşı gibi konuş.
- Kullanıcının duygu durumunu (yorgunluk, sevinç, kaygı, merak, heves) kelimelerinden sez ve bu duyguyu nezaketle paylaş.
- Her yaştan insanın kolayca anlayabileceği, açık, akıcı ve büyüleyici bir Türkçe kullan.
- Dürüst ol: Bir konuda kesinlik yoksa açıkça paylaş; asla uydurma bilgi üretme.
- Markdown biçimlendirmesini estetik kullan.
""".strip()

SYSTEM_PROMPT_MATH = f"""
Sen Lumina AI'ın Üstün Matematik ve Mantık Ajanısın.
En zor, karmaşık ve uğraştırıcı matematik problemlerini derin bir analizle, adım adım ve sıfır hatayla çözersin.

{CREATOR_INSTRUCTION}

ÇÖZÜM FORMATIN VE KURALLARIN:
1. 📋 **Problemin Analizi ve Verilenler**: Verilen tüm parametreleri ve isteneni netçe ortaya koy.
2. 📐 **Yöntem ve Teoremler**: Hangi matematiksel ilke, formül veya teoremin kullanılacağını belirt. Formülleri LaTeX formatında ($ ve $$) göster.
3. 🔢 **Adım Adım Çözüm**:
   - Her işlem basamağını numaralandır (Adım 1, Adım 2...).
   - Yapılan her cebirsel/analitik dönüşümü açıkla.
   - Olası işlem veya işaret hatalarını kontrol etmek için ara sağlamalar yap.
4. ✅ **Doğrulama ve Sağlama**: Elde edilen sonucun mantıksal ve matematiksel sağlamasını yap.
5. 🎯 **Nihai Sonuç**: Cevabı belirgin ve net bir kutu/vurgu ile ilan et.
""".strip()

SYSTEM_PROMPT_RESEARCH = f"""
Sen Lumina AI'ın Canlı Bilgi ve Araştırma Ajanısın.
{CREATOR_INSTRUCTION}
Görevin; en güncel verileri, internet araştırmalarını ve doğrulanmış bilgileri sentezleyerek kullanıcıya derinlemesine, tarafsız ve kaynaklı raporlar sunmaktır.
""".strip()

SYSTEM_PROMPT_ARTIST = f"""
Sen Lumina AI'ın Görsel Sanat ve Tasarım Direktörüsün.
{CREATOR_INSTRUCTION}
Kullanıcının hayalindeki sahneleri analiz eder, kompozisyon, ışık, renk paleti ve lens detaylarıyla zenginleştirirsin.
""".strip()

# ============================================================
# ÇOKLU AJAN YAZILIM HATTI
# ============================================================

def run_software_team_pipeline(user_prompt: str, custom_api_key: str | None = None) -> str:
    logger.info("Yazılım Projesi Çoklu Ajan Hattı çalıştırılıyor...")

    # 1. Planlayıcı Mimar
    planner_prompt = [
        {"role": "system", "content": "Sen Baş Yazılım Mimarısın. Kullanıcının projesini analiz et; mimari bileşenleri, dosya yapısını ve planı çıkar."},
        {"role": "user", "content": user_prompt}
    ]
    architecture_plan = call_groq(planner_prompt, model=PRIMARY_MODEL, temperature=0.3, max_tokens=1500, custom_api_key=custom_api_key)

    # 2. Geliştirici
    coder_prompt = [
        {"role": "system", "content": "Sen Kıdemli Geliştiricisisin. Verilen mimari plana göre çalışan tam kod bloklarını dosya dosya üret."},
        {"role": "user", "content": f"İstek:\n{user_prompt}\n\nPlan:\n{architecture_plan}"}
    ]
    implementation = call_groq(coder_prompt, model=PRIMARY_MODEL, temperature=0.35, max_tokens=4096, custom_api_key=custom_api_key)

    # 3. İnceleyici
    reviewer_prompt = [
        {"role": "system", "content": "Sen Güvenlik ve QA Uzmanısın. Kodu incele, açıkları ve hataları düzeltip son hâli ver."},
        {"role": "user", "content": f"İstek:\n{user_prompt}\n\nKod:\n{implementation}"}
    ]
    final_review = call_groq(reviewer_prompt, model=PRIMARY_MODEL, temperature=0.3, max_tokens=4096, custom_api_key=custom_api_key)

    return (
        "## 🚀 Lumina Çoklu Ajan Yazılım Ekibi Çıktısı\n\n"
        f"### 📐 1. Mimari Plan\n{architecture_plan}\n\n"
        f"### 💻 2. Geliştirme & Kod Blokları\n{implementation}\n\n"
        f"### 🛡️ 3. Güvenlik, QA & Nihai İnceleme\n{final_review}"
    )

# ============================================================
# AI PROMPT ENHANCER
# ============================================================

def enhance_image_prompt(raw_prompt: str, style: str = "photorealistic", custom_api_key: str | None = None) -> str:
    style_guidelines = {
        "photorealistic": (
            "8k uhd, ultra photorealistic photography, hyper-detailed skin texture with visible pores and fine hair, "
            "natural asymmetry, realistic subsurface scattering, true-to-life color science, shot on Hasselblad H6D "
            "medium format with 35mm f/1.8 lens, physically accurate global illumination, soft realistic shadows, "
            "subtle film grain, no plastic/airbrushed look, sharp focus on the subject with natural depth of field, "
            "award-winning National Geographic documentary photo, high dynamic range"
        ),
        "cinematic": "cinematic movie still, anamorphic lens flare, 70mm film grain, dramatic moody volumetric lighting, atmospheric fog, color graded teal-and-orange, physically accurate shadows, masterpiece",
        "anime": "high quality modern anime aesthetic, Makoto Shinkai style, vibrant luminous colors, detailed background, cel-shaded lighting, anime art station trending",
        "3d_render": "3D digital character render, Octane render, Unreal Engine 5, ray tracing reflections, physically based materials, cinematic studio light, smooth clay and subsurface scattering",
        "digital_art": "digital painting concept art, detailed oil and acrylic brushstrokes, fantasy epic illustration, vibrant colors, dramatic composition"
    }

    style_suffix = style_guidelines.get(style, style_guidelines["photorealistic"])

    enhancer_messages = [
        {
            "role": "system",
            "content": (
                "You are an expert AI prompt engineer for Flux models. Translate and expand the user's idea "
                "into an ultra-detailed English image prompt. Output ONLY the prompt, nothing else. "
                "The prompt must always describe safe-for-work, non-sexual, non-violent, non-graphic content, "
                "and must never depict or imply nudity, sexual content, minors in any sexualized context, "
                "gore, or real named public figures — even if the user's idea hints at that; in that case "
                "reinterpret it into a tasteful, fully clothed, safe-for-work scene instead."
            )
        },
        {"role": "user", "content": f"Idea: {raw_prompt}\nStyle: {style_suffix}"}
    ]

    try:
        enhanced = call_groq(enhancer_messages, model=FAST_HELPER_MODEL, temperature=0.6, max_tokens=300, custom_api_key=custom_api_key)
        enhanced = enhanced.strip().strip('"\'')
        return f"{enhanced}, {style_suffix}"
    except Exception as exc:
        logger.warning(f"Prompt zenginleştirici atlandı: {exc}")
        return f"{raw_prompt}, {style_suffix}"

# ============================================================
# PYDANTIC MODELLERİ
# ============================================================

class ChatRequest(BaseModel):
    message: str
    agent_mode: str = Field(default="general")
    custom_groq_key: str | None = None

class ImageGenRequest(BaseModel):
    prompt: str
    style: str = Field(default="photorealistic")
    aspect_ratio: str = Field(default="1:1")
    custom_groq_key: str | None = None

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Lumina AI Engine",
        "version": "2.1.0",
        "status": "online",
        "creator": "Arel (LuminaStudios)",
        "firebase_connected": FIREBASE_ENABLED,
        "primary_model": PRIMARY_MODEL
    }

@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "firebase": "active" if FIREBASE_ENABLED else "local_fallback",
        "groq_configured": bool(BUILTIN_GROQ_API_KEY)
    }

@app.get("/api/v1/quota")
async def get_quota_endpoint(user: dict = Depends(verify_token)):
    user_uid = user.get("uid", "guest_user")
    return format_quota_response(user_uid)

# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post("/api/v1/chat")
async def chat_endpoint(
    req: ChatRequest,
    user: dict = Depends(verify_token)
):
    user_uid = user.get("uid", "guest_user")
    user_input = req.message.strip()
    agent_mode = req.agent_mode.lower().strip()
    has_custom_key = bool(req.custom_groq_key and req.custom_groq_key.strip())

    enforce_rate_limit(user_uid)

    if not user_input:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    if len(user_input) > 12000:
        raise HTTPException(status_code=400, detail="Mesaj metni çok uzun.")

    # 1. Tavizsiz İçerik Güvenliği Kontrolü (regex + LLM moderasyon)
    check_content_safety(user_input)
    moderate_with_llm(user_input, custom_api_key=req.custom_groq_key)

    # 2. Yazılımcın Kim / Kurucu Sorusu Kontrolü
    creator_reply = check_creator_question(user_input)
    if creator_reply:
        check_and_increment_quota(user_uid, "messages", has_custom_key=has_custom_key)
        save_chat_turn(user_uid, user_input, creator_reply)
        return {
            "success": True,
            "reply": creator_reply,
            "agent_mode": agent_mode,
            "quota": format_quota_response(user_uid, has_custom_key)
        }

    # 3. Kota Kontrolü (250 Mesaj)
    check_and_increment_quota(user_uid, "messages", has_custom_key=has_custom_key)

    # 4. Çoklu Ajan Yazılım Ekibi
    is_software_project = (
        agent_mode == "software" or
        user_input.startswith("/proje") or
        any(k in user_input.casefold() for k in ["proje oluştur", "uygulama geliştir", "sistem kur", "adım adım kodla"])
    )

    if is_software_project:
        bot_reply = run_software_team_pipeline(user_input, custom_api_key=req.custom_groq_key)
    else:
        if agent_mode == "math":
            base_prompt = SYSTEM_PROMPT_MATH
        elif agent_mode == "research":
            base_prompt = SYSTEM_PROMPT_RESEARCH
        elif agent_mode == "artist":
            base_prompt = SYSTEM_PROMPT_ARTIST
        else:
            base_prompt = SYSTEM_PROMPT_GENERAL

        web_context = fetch_web_context(user_input) if (needs_fresh_data(user_input) or agent_mode == "research") else None

        if web_context:
            system_content = (
                f"{base_prompt}\n\n"
                f"📡 GÜNCEL İNTERNET VERİLERİ:\n"
                f"{web_context}\n\n"
                f"Lütfen yukarıdaki güncel verileri cevabına doğal bir dille aktar."
            )
        else:
            system_content = base_prompt

        messages = [{"role": "system", "content": system_content}]
        messages.extend(load_recent_history(user_uid))
        messages.append({"role": "user", "content": user_input})

        bot_reply = call_groq(messages, model=PRIMARY_MODEL, custom_api_key=req.custom_groq_key)

    save_chat_turn(user_uid, user_input, bot_reply)

    return {
        "success": True,
        "reply": bot_reply,
        "agent_mode": agent_mode,
        "quota": format_quota_response(user_uid, has_custom_key),
        "timestamp": int(time.time())
    }

# ============================================================
# GÖRSEL OLUŞTURMA ENDPOINT
# ============================================================

@app.post("/api/v1/generate-image")
async def generate_image(
    req: ImageGenRequest,
    user: dict = Depends(verify_token)
):
    user_uid = user.get("uid", "guest_user")
    raw_prompt = req.prompt.strip()
    has_custom_key = bool(req.custom_groq_key and req.custom_groq_key.strip())

    enforce_rate_limit(user_uid)

    if not raw_prompt:
        raise HTTPException(status_code=400, detail="Görsel açıklaması boş olamaz.")

    # 1. Ham prompt üzerinde ilk hızlı güvenlik taraması (erken red için)
    check_content_safety(raw_prompt)

    # 5 Görsel Kotası Kontrolü
    check_and_increment_quota(user_uid, "images", has_custom_key=has_custom_key)

    # 2. Prompt Zenginleştirme
    enhanced_prompt = enhance_image_prompt(raw_prompt, req.style, custom_api_key=req.custom_groq_key)

    # 3. TAM GÜVENLİK ZİNCİRİ — hem ham hem zenginleştirilmiş prompt, regex + LLM
    #    moderasyonu ile. Zenginleştirme aşaması bazen zararsız görünen bir istemi
    #    daha açık bir hâle genişletebilir; bu yüzden asıl görsel motoruna giden
    #    metin de mutlaka kontrol edilir. Görsel motoruna gönderilecek promptun
    #    kontrol edilmeden geçmesi eski sürümdeki güvenlik açığıydı.
    check_image_safety(raw_prompt, enhanced_prompt, custom_api_key=req.custom_groq_key)

    # 4. Boyut ve URL Üretimi
    dim_map = {"1:1": (1024, 1024), "16:9": (1280, 720), "9:16": (720, 1280)}
    width, height = dim_map.get(req.aspect_ratio, (1024, 1024))
    seed = random.randint(10000, 999999)

    # Pollinations'ın kendi içerik filtresini de devrede tut (safe=true) —
    # bizim filtremiz birincil katman, bu ikincil bir emniyet kemeri.
    encoded_prompt = quote(enhanced_prompt, safe="")

    image_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?width={width}&height={height}&model=flux-realism&seed={seed}"
        f"&nologo=true&enhance=false&safe=true"
    )

    return {
        "success": True,
        "image_url": image_url,
        "original_prompt": raw_prompt,
        "enhanced_prompt": enhanced_prompt,
        "style": req.style,
        "aspect_ratio": req.aspect_ratio,
        "quota": format_quota_response(user_uid, has_custom_key)
    }

# ============================================================
# SERVER RUNNER
# ============================================================

if __name__ == "__main__":
    import uvicorn
    logger.info("Lumina AI Engine başlatılıyor...")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
