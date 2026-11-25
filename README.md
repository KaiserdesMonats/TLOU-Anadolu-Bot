# 🧟‍♂️ TLOU Anadolu Discord Botu

The Last of Us tarzı zombi kıyameti RP sunucusu için Python Discord botu.

## 📦 İçindekiler

```
tlo-bot/
├── .env                  # Bot token ve Guild ID (GİZLİ - Render'da env var)
├── .env.example          # Örnek .env
├── .gitignore
├── .github/workflows/    # GitHub Actions (syntax check + keep-alive)
│   ├── syntax-check.yml  # Her push'ta otomatik test
│   └── keep-alive.yml     # Yedek 7/24 ping
├── .replit               # Replit ayarları (yedek yöntem)
├── Procfile              # Render/Railway başlatma komutu
├── render.yaml           # Render.com ayarları ⭐
├── runtime.txt           # Python sürümü (3.11.9)
├── keep_alive.py         # Flask web sunucusu (Replit yedek için)
├── README.md             # Bu dosya
├── main.py               # Bot başlatma
├── config.py             # Tüm ayarlar ve ID'ler
├── database.py           # SQLite veritabanı (aiosqlite)
├── requirements.txt      # Python bağımlılıkları
├── cogs/                 # Komut modülleri (13 adet)
│   ├── kayit.py          # /kayit
│   ├── profil.py         # /profil
│   ├── envanter.py       # /envanter, /slot-gelistir
│   ├── meslek.py         # /meslek, /yankesicilik
│   ├── yagma.py          # /yagma, /arastir, /enfekte-temizle
│   ├── uretim.py         # /uretim
│   ├── enfeksiyon.py     # /enfeksiyon, /asi-uret vb.
│   ├── cete.py           # /cete-* komutları
│   ├── event.py          # /event-baslat
│   ├── admin.py          # /admin-*
│   ├── hava_durumu.py    # Günlük hava durumu (cron)
│   ├── tasks.py          # Arka plan görevleri
│   └── yardim.py         # /yardim
└── utils/                # Yardımcı modüller
    ├── embeds.py         # Embed şablonları
    ├── localization.py   # Mesaj sabitleri
    ├── formatting.py     # Formatlama araçları
    ├── checks.py         # Yetki kontrolleri
    └── constants.py      # Eşya listeleri, meslekler vb.
```

---

## 🚀 Ana Yöntem: GitHub + Render.com (ÜCRETSİZ 7/24) ⭐

Bu yöntem Replit'e göre daha stabil. Render, GitHub deposunu otomatik çeker ve botu çalıştırır.

### Adım 1: GitHub'a Repo Oluştur

1. [github.com](https://github.com)'a giriş yap
2. Sağ üstten **`+` → New repository**
3. Repo adı: `tlou-anadolu-bot`
4. **Private** seç (token gizli kalacak)
5. "Create repository"

### Adım 2: Kodları GitHub'a Yükle

```bash
# Bilgisayarında (ya da Replit Shell'de):
git init
git add .
git commit -m "TLOU Anadolu Bot - ilk sürüm"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/tlou-anadolu-bot.git
git push -u origin main
```

Veya GitHub web arayüzünden ZIP içeriğini manuel yükle.

### Adım 3: Render.com'da Hesap Aç

1. [render.com](https://render.com)'a git
2. **Sign Up** → **GitHub ile giriş yap** (en kolayı)
3. Render senin GitHub repolarına erişim isteyecek → onayla

### Adım 4: Botu Deploy Et

1. Render dashboard → **New +** → **Background Worker**
   - **(Web Service DEĞİL — Background Worker seç!)**
   - Çünkü bot web trafiği değil, arka plan görevi
2. **Connect a repository** → `tlou-anadolu-bot`'u seç
3. Ayarları doldur:
   - **Name**: `tlou-anadolu-bot`
   - **Region**: Frankfurt (Türkiye'ye en yakın)
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Instance Type**: Free
4. **Environment Variables** (ÇOK ÖNEMLİ):
   - `BOT_TOKEN` = `senin_gerçek_bot_tokenin`
   - `GUILD_ID` = `1470543732033191986`
5. **Create Background Worker**

### Adım 5: Bekle ve Çalıştır

- Render bağımlılıkları yükler (2-3 dakika)
- Bot otomatik başlar
- Logları Render dashboard'dan görebilirsin
- Bot 7/24 çalışır!

### Adım 6: UptimeRobot (Opsiyonel Yedek)

Render free tier'da bot bazen durabilir. Yedek için:
1. [UptimeRobot](https://uptimerobot.com)'a kayıt ol
2. Render sana bir URL verir (web servisiysen) — ama Background Worker URL vermez
3. Bu yüzden Render'ı **Web Service** olarak kur, `keep_alive.py` otomatik çalışır

**Web Service seçersen:**
- **Start Command**: `python main.py` (keep_alive otomatik başlar)
- Render sana URL verir: `https://tlou-anadolu-bot.onrender.com`
- Bu URL'yi UptimeRobot'a ekle (5 dakika ping)

---

## 🔄 Alternatif: Replit + UptimeRobot

Render yerine Replit kullanmak istersen:

1. [replit.com](https://replit.com)'a ZIP yükle
2. `.env` dosyasına token yaz
3. `pip install -r requirements.txt`
4. `python main.py` ile başlat
5. Replit URL'sini al: `https://[replit-adi].[kullanici].repl.co`
6. UptimeRobot'a bu URL'yi ekle (5 dakika ping)

Replit free tier'da 5 dakika işlem yapmazsa uyur. UptimeRobot ping atınca uyanır.

---

## ⚙️ Bot Ayarları

### Discord Developer Portal
1. [Discord Developer Portal](https://discord.com/developers/applications)'a git
2. Bot oluştur
3. **Intents** sekmesinden şunları AÇ:
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT
   - ✅ PRESENCE INTENT
4. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: Administrator (ya da aşağıdakiler):
     - Manage Roles
     - Manage Channels
     - Send Messages
     - Embed Links
     - Use Slash Commands
     - Add Reactions
5. Botu sunucuna davet et

### Sunucu Hazırlığı
Bot çalışmadan önce sunucunda şunlar olmalı:
- Tüm roller (config.py'deki ID'lerle)
- Tüm kanallar (config.py'deki ID'lerle)
- Bot rolü, kendi rolü pozisyonda üstte olmalı (rolleri yönetebilmek için)

---

## 🔧 Sık Karşılaşılan Sorunlar

### "Improper token has been passed"
`.env` (Render'da environment variables) içindeki `BOT_TOKEN` yanlış.

### "Missing Access"
Bot'un sunucuda yeterli yetkisi yok. Botu Administrator izni ile davet et.

### "Cog yuklenemedi: ModuleNotFoundError"
`cogs/__init__.py` ve `utils/__init__.py` dosyaları boş bile olsa OLMALI.

### Komutlar görünmüyor (slash komutlar)
Bot ilk başladığında komutlar senkronize edilir. 1-2 dakika bekle.
Hala görünmüyorsa: Botu Discord'dan atıp yeniden davet et.

### Render: "Build failed"
`requirements.txt`'teki sürümü kontrol et. `discord.py==2.3.2` olmalı.

### Render: Bot durdu
Free tier 750 saat/ay verir. Genelde yeterli. Eğer durursa:
- Render dashboard → Manual deploy → "Clear build cache & deploy"
- Veya yeni commit pushla (otomatik yeniden deploy)

---

## 📊 Veritabanı

Bot `tlo_bot.db` adında SQLite veritabanı kullanır. Otomatik oluşturulur.
**Render'da**: Render her deploy'da dosyaları sıfırlar, yani DB sıfırlanır!
Bu yüzden Render'da kalıcı DB için:
- Render'da **Disk** ekle (ücretli)
- Veya PostgreSQL'e geç (database.py'yi düzenle)

**Replit'te**: DB korunur, ama Replit silinirse gider.

**Çözüm**: Düzenli DB yedeği al (`tlo_bot.db`'yi indir).

---

## 📝 Komutlar

Toplam **47 komut**. Tüm listeyi görmek için:
```
/yardim          → tüm kategoriler
/yardim <kat>    → kategori detayı
/komutlar        → kısa liste
/hakkinda        → bot bilgisi
```

---

## 🆘 Yardım

Sorun yaşarsan:
1. `bot.log` dosyasını kontrol et (Render/Replit loglarında)
2. Hata mesajını oku
3. İlgili cog dosyasını aç ve kontrol et

---

## 📜 Hosting Karşılaştırması

| Platform | Maliyet | 7/24 | DB Kalıcılık | Zorluk |
|---|---|---|---|---|
| **Render.com** ⭐ | Ücretsiz (750s) | Evet | Hayır (ücretsiz) | Kolay |
| Replit + UptimeRobot | Ücretsiz | Evet | Evet | Orta |
| Railway | $5/ay kredi | Evet | Evet | Kolay |
| VPS (DigitalOcean) | ~$5/ay | Evet | Evet | Zor |
| Kendi bilgisayar | Ücretsiz | Hayır | Evet | Kolay |

**Öneri**: Render.com + UptimeRobot kombinasyonu.

---

## 📜 Lisans

Bu proje TLOU Anadolu sunucusu için özel geliştirilmiştir.
# TLOU-Anadolu-Bot
# TLOU-Anadolu-Bot
# TLOU-Anadolu-Bot
# TLOU-Anadolu-Bot
