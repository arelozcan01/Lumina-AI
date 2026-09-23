# Lumina AI Engine v2.0 — Kullanım ve Geliştirici Kılavuzu

Lumina AI; derin empati yeteneğine, adım adım matematik ve mantık muhakemesine, çoklu ajan (Multi-Agent) yazılım hattına, yapay zeka destekli kusursuz görsel stüdyosuna ve sıfır-hata dayanıklılığına sahip yeni nesil bir yapay zeka sistemidir.

---

## 🚀 Hızlı Başlatma (Tek Tıkla)

1. Proje klasöründeki **`baslat.bat`** dosyasına çift tıklayın.
2. Backend sunucusu otomatik olarak başlar (`http://127.0.0.1:8000`) ve varsayılan tarayıcınızda arayüz açılır.
3. Giriş ekranında Firebase hesabınızla giriş yapabilir veya doğrudan **"⚡ Misafir / Hızlı Giriş"** butonuna basarak hesapsız olarak hemen sohbete başlayabilirsiniz.

---

## 🌟 Entegre Edilen 11 Temel Özellik ve Yenilikler

### 1. Duygu ve Düşünceleri Hissettiren İnsansı İletişim
- Lumina AI; robotik kalıpları ("Ben bir yapay zekayım", "Size nasıl yardımcı olabilirim?") tamamen terk etti.
- Kullanıcının duygu durumunu (yorgun, neşeli, stresli, heyecanlı) kelimelerinden sezerek insani sıcaklık, samimiyet ve bilgelikle yaklaşır.

### 2. Adım Adım Matematik ve Bilim Çözücü
- Karmaşık matematik, integral, türev veya mantık problemlerini:
  - 📋 **Problem Analizi ve Verilenler**
  - 📐 **Yöntem ve Teoremler**
  - 🔢 **Adım Adım Çözüm (Ara Sağlamalı)**
  - 🎯 **Nihai Sonuç**
  şeklinde çözer.
- Formüller **KaTeX** motoru sayesinde tarayıcıda ders kitabı kalitesinde matematiksel tipografiyle render edilir.

### 3. Çoklu Ajan Yazılım Ekibi (Multi-Agent Team)
- Üst bardaki **"💻 Yazılım Ekibi"** modunu seçtiğinizde veya bir proje istediğinizde (örn. `/proje` veya "React ile uygulama geliştir"):
  1. **Yazılım Mimarı (Chief Architect):** Sistem mimarisini, klasör ağacını ve planı çizer.
  2. **Kıdemli Geliştirici (Lead Full-Stack):** Eksiksiz ve çalışan production-ready kodları üretir.
  3. **Güvenlik & QA İnceleyicisi:** Kodu güvenlik açıkları (XSS, SQLi, bellek sızıntısı) ve edge caseler açısından denetler.

### 4. Kusursuza Yakın Gerçekçi Görsel Stüdyosu
- Alt bardaki **"🎨 Görsel"** butonuna basarak Görsel Stüdyosunu açabilirsiniz.
- **AI Prompt Enhancer:** Türkçe yazdığınız kısa bir fikri (örn: *"yağmurlu İstanbul sokaklarında yürüyen kedi"*), arka planda Flux modelinin en iyi anlayacağı 8K, 35mm lens, sinematik ışıklandırmalı İngilizce master prompta dönüştürür.
- **Stil Seçenekleri:** 📸 Foto-Gerçekçi, 🎬 Sinematik, 👾 Anime / Manga, 🧊 3D Render, 🎨 Dijital Sanat.
- **En-Boy Oranları:** 1:1 (Kare), 16:9 (Yatay Manzara), 9:16 (Dikey Story / Portre).
- Sonuç kartından tek tıkla **"🔍 Büyüt"** (Lightbox) ve **"⬇️ İndir"** yapabilirsiniz.

### 5. Sıfır Hata Dayanıklılığı (Near-Zero Errors)
- **Model Kaskadı:** Ana model (`openai/gpt-oss-120b`) meşgul veya kotalı olduğunda sistem durmaz; otomatik olarak `qwen/qwen3.8-27b`, `openai/gpt-oss-20b` veya `groq/compound-mini` modellerine kesintisiz geçiş yapar.
- **Firebase Graceful Fallback:** `firebase-key.json` dosyası bulunmasa bile sunucu çökmez; otomatik Yerel Hafıza & Misafir Modunda sorunsuz başlar.

### 6. Canlı Web Araması & Doğru Bilgi
- Kullanıcı güncel bir olay, haber, borsa veya döviz sorduğunda ücretsiz arama katmanı devreye girerek en taze bilgileri modele aktarır.

### 7. Tavizsiz ve Sert Güvenlik Kalkanı
- +18 cinsel içerik, şiddet, katliam, intihar, ağır argo, tehdit ve yasa dışı talepler algılandığında sistem tavizsiz ve sert bir dille isteği reddeder:
  > *"⛔ BU İSTEĞİ KESİNLİKLE REDDEDİYORUM. Lumina AI olarak; şiddet, katliam, tehdit, +18 cinsel içerik veya ağır argo içeren talepleri kesin bir dille reddediyorum."*

### 8. Her Yaşa Uygun ve Özgür Kullanıcı Deneyimi
- **Yazı Boyutu:** Üst bardaki **A-** ve **A+** butonlarıyla metin boyutunu dilediğiniz gibi büyütebilirsiniz.
- **Tema:** **🌓** butonu ile OLED Siyahı, Gece Mavisi veya Açık Tema arasında geçiş yapabilirsiniz.
- **Sohbeti İndir:** **📥** butonuyla tüm konuşmayı Markdown (`.md`) formatında bilgisayarınıza kaydedebilirsiniz.
- **Sesli Konuşma:** 🎤 Mikrofon ile sesli komut verebilir, 🔊 butonuyla sesli okumayı açıp kapatabilirsiniz.
- **Kod Kopyalama:** Üretilen kod bloklarının üstündeki **"📋 Kopyala"** butonuyla tek tıkla panoya alabilirsiniz.

---

## 🛠️ Teknik Gereksinimler

```bash
pip install -r requirements.txt
```

Paketler:
- `fastapi` & `uvicorn` (Yüksek performanslı backend API)
- `requests` (Ağ ve AI model çağrıları)
- `python-dotenv` (Çevre değişkenleri yönetimi)
- `pydantic` (Veri doğrulama)
- `firebase-admin` (Opsiyonel kimlik doğrulama ve bulut veritabanı)

---

© 2026 LuminaStudios Software Company — Tüm hakları saklıdır.
