"""
config.py — TLOU Anadolu Bot Yapılandırması
Tüm Discord Rol/Kanal ID'leri, oyun sabitleri ve yetki grupları burada.
Kaynak: Sunucudan export edilen roles_*.csv ve channels_*.csv dosyaları.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# DISCORD BOT AYARLARI
# ═══════════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))

# Prefix — sabit, değiştirilemez
PREFIX = "tlo."

# ═══════════════════════════════════════════════════════════════════
# OYUN AYARLARI
# ═══════════════════════════════════════════════════════════════════
# Zaman ölçeği: 1 gerçek gün = 1 RP günü

# Çete sınırları
MAX_NORMAL_CETE = 2          # Aynı anda maksimum normal çete
MAX_TARIKAT_CETE = 2          # Aynı anda maksimum tarikat çetesi
MAX_MILIS_CETE = 2            # Aynı anda maksimum milis grubu

# Hava durumu
HAVA_DURUMU_SAATI = 21        # Her gün saat 21:00'de atılır
GEC_BOT_SAATI = 21            # 21:00 sonrası otomatik mesaj yok

# Hayatta kalma — başlangıç değerleri
BASLANGIC_CAN = 100
BASLANGIC_ACLIK = 100
BASLANGIC_SUSUZLUK = 100
BASLANGIC_PARA = 100
BASLANGIC_SLOT = 10

# Envanter geliştirme (4 seviye)
SLOT_GELISTIRME_SEVIYELERI = [
    # (slot_sayisi, para_maliyeti)
    (15, 500),    # 1. seviye: 15 slot, 500 🪙
    (20, 1200),   # 2. seviye: 20 slot, 1200 🪙
    (25, 2500),   # 3. seviye: 25 slot, 2500 🪙
    (30, 5000),   # 4. seviye: 30 slot, 5000 🪙
]

# Yaş sınırı (kayıt)
MIN_YAS = 15
MAX_YAS = 80

# Cooldown'lar (saniye)
CD_YAGMA = 3 * 60 * 60              # 3 saat (global: /yagma, /arastir, /enfekte-temizle)
CD_MESLEK = 60 * 60                  # 1 saat (meslek eylemleri)
CD_YANKESICILIK = 2 * 60 * 60        # 2 saat (çete yankesicilik)
CD_RITUEL = 6 * 60 * 60              # 6 saat (tarikat ritüeli)

# Enfeksiyon (4 aşamalı zombileşme)
ENFEKSIYON_ASAMA_SAYISI = 4
ENFEKSIYON_TOPLAM_SURE = 72 * 60 * 60   # 72 saat (3 gün) toplam
ENFEKSIYON_ASAMA_SURESI = ENFEKSIYON_TOPLAM_SURE // ENFEKSIYON_ASAMA_SAYISI  # 18 saat/aşama

# Aşama isimleri (hala insan, dönüşüyor)
ENFEKSIYON_ASAMA_ISIMLERI = {
    1: "Başlangıç (Hafif)",
    2: "Yaygın (Orta)",
    3: "İlerlemiş (Ağır)",
    4: "Kritik (Dönüşüm Eşiği)",
}

# Permadeath
PERMADEATH_KARANTINA_GUN = 3      # Ölen karakter 3 gün sonra DB'den gerçekten silinir

# Çete ekonomisi
CETE_KAN_BAGI_PARA = 100         # Yeni üye giriş ücreti (🪙)
CETE_PASIF_GELIR = 150           # Her 24 RP saatinde kasaya otomatik para
CETE_PASIF_GELIR_ARALIK = 24 * 60 * 60  # 24 saatte bir
CETE_BASKIN_HAZIRLIK_SAAT = 12   # Baskın hazırlık süresi
CETE_BASKIN_GANIMET_ORANI = 0.30 # Kazanan, kaybedenin kasasından maks %30 alır
CETE_BASKIN_SEKTOR_ETKI = 0.20   # Admin RP kalitesine göre ±%20 etki

# Haraç / Vergi (bölge kontrolü)
HARAC_MIN_ORAN = 0.10            # En az %10
HARAC_MAX_ORAN = 0.15            # En fazla %15
HARAC_SABIT_PARA = 50            # veya sabit 50 🪙

# Üye başına haraç seviyesi (lider/subay /cete-harac-ayarla ile ayarlar)
# seviye -> {ad: gorunen ad, oran: kazancdan kesilecek pay}
HARAC_SEVIYELERI = {
    0: {"ad": "Haraç Yok",     "oran": 0.00, "emoji": "🕊️"},
    1: {"ad": "Düşük Haraç",   "oran": 0.05, "emoji": "🪙"},
    2: {"ad": "Orta Haraç",    "oran": 0.10, "emoji": "💰"},
    3: {"ad": "Yüksek Haraç",  "oran": 0.15, "emoji": "🏴"},
}

# Yankesicilik
YANKESICILIK_BASARI_ORANI = 0.50  # %50 başarı şansı

# Event cooldown (aynı tür 3-4 RP günü tekrar etmez)
EVENT_CD_GUN = 3
EVENT_CD_SANIYE = EVENT_CD_GUN * 24 * 60 * 60

# Aşı üretimi (doktor)
ASI_MALZEME_SAYISI = 5           # 1 aşı için gereken nadir malzeme sayısı

# ═══════════════════════════════════════════════════════════════════
# YETKİ GRUPLARI
# ═══════════════════════════════════════════════════════════════════
# Admin (Yönetici Ekip): Tüm admin komutları + tüm yetki gruplarına erişim
ADMIN_ROLES = {
    1470544130559049921,  # ♔ • Creator
    1470743025280880743,  # ♕ • Boss
    1518268192395497544,  # 👑 • Administrator
    1518268274687873145,  # 🛡️ • Admin
    1518267799200338091,  # 🛡️ • Kıdemli Moderatör
    1518378716533882921,  # 🎩 • Yönetici Ekip
    1492516693921234964,  # ⚖️ • Moderatör
}

# RP Yetkilisi: RP ile alakalı komutlar (event, bölge kilitle, enfeksiyon müdahale)
# Adminler otomatik dahil
RP_YETKILI_ROLES = {
    1569011228959834182,  # 📋 • RP Yetkilisi
} | ADMIN_ROLES

# Kayıt Yetkilisi: Sadece /kayıt komutu
# Adminler otomatik dahil
KAYIT_YETKILI_ROLES = {
    1470748590917025842,  # 🪪 • Kayıt Yetkilisi
} | ADMIN_ROLES

# ═══════════════════════════════════════════════════════════════════
# TEMEL ROLLER
# ═══════════════════════════════════════════════════════════════════
ROL_EVERYONE        = 1470543732033191986
ROL_UYE             = 1568945668687528028   # 👤 • Üye
ROL_KAYITSIZ        = 1470747472858058897   # 🚪 • Kayıtsız
ROL_BOT             = 1492819034305990737   # 🤖 • Bot
ROL_BOT_KENDISI     = 1569076991095865418   # The Last Of Us Anadolu

# Bildirim rolleri
ROL_PARTNER_BILDIRIMI = 1515793349603492081
ROL_RADYO_BILDIRIMI   = 1523997096175337472
ROL_DUYURU_BILDIRIMI  = 1515797414223675413

# Özel roller
ROL_OZEL_UYE    = 1518271196154691644
ROL_ILK_UYE     = 1494999628515643455
ROL_GAZETECI    = 1492555591007211781
ROL_HARITACI    = 1497684152512676030
ROL_SUNUCU_EKIBI = 1470743726958706831

# ═══════════════════════════════════════════════════════════════════
# ŞEHİR ROLLERİ (kayıt dropdown için)
# ═══════════════════════════════════════════════════════════════════
SEHIR_ROLLERI = {
    "İstanbul": 1571192565385003008,
    "Ankara":   1571192620758339787,
    "İzmir":    1571192697837064334,
    "Bursa":    1571192891273904168,
    "Konya":    1571192938912948364,
    "Antalya":  1571192985180315658,
    "Adana":    1571193522751676496,
    "Trabzon":  1571193586048049335,
    "Samsun":   1571193638254280845,
    "Denizli":  1571193726573740184,
}

# ═══════════════════════════════════════════════════════════════════
# MESLEK GRUPLARI (RP Oyuncusu kayıt dropdown için)
# ═══════════════════════════════════════════════════════════════════
# Not: Lider rolleri (Çete Lideri, Mürşit, Milis Grubu Lideri) kayıtta VERİLMEZ.
#       Çete kurulumu onaylanınca lider rolü liderliğe verilir, üyelerine normal üye rolü verilir.
MESLEK_GRUPLARI = {
    "Valilik": [
        ("Vali",                                   1569758177321418792),
        ("Vali Yardımcısı",                        1569758237396443157),
        ("Tahsis ve Halkla İlişkiler Memuru",      1569758292501340330),
    ],
    "Hükümet Askeri": [
        ("Bölge Komutanı",                 1569758830970015834),
        ("Yüzbaşı",                         1569758897273704488),
        ("Uzman Çavuş",                     1569759025677992088),
        ("Er",                              1569759135308709918),
        ("Lojistik ve İstihkam Personeli",  1569759192087142601),
    ],
    "Bağımsız Askeri": [
        ("Bağımsız Komutan",          1569759704446533733),
        ("Paralı Asker / Şok Timi",   1569759777867960461),
        ("Keskin Nişancı",            1569759846536839218),
        ("Öncü Keşif Birliği",        1569759904078635150),
        ("Bağımsız Lojistik Destek",  1569759955873955953),
    ],
    "Polis": [
        ("Emniyet Amiri / Komiser",        1569760484591140904),
        ("Çevik Kuvvet / Özel Harekat",    1569760545953816597),
        ("Devriye Ekibi",                  1569760596851687434),
        ("Trafik ve İletişim Sorumlusu",   1569760641516970104),
    ],
    "Çiftçi": [
        ("Baş Çiftçi",    1569761112830902414),
        ("Tarla İşçisi",  1569761186172506153),
        ("Çoban",          1569761244737441822),
    ],
    "Tamirci": [
        ("Mühendis",                      1569761537584013393),
        ("Araç ve Jeneratör Uzmanı",      1569761599613305034),
        ("Çırak",                         1569761650008129656),
    ],
    "Doktor": [
        ("Başhekim / Cerrah",          1569762333914439781),
        ("Eczacı",                     1569765127316840520),
        ("Hemşire / İlk Yardımcı",     1569765212372861058),
        ("Araştırmacı / Patolog",       1569765270858367136),
    ],
    "Normal Çete": [
        ("Savaşçı / Yağmacı",     1569766798881063032),
        ("Haberci / Casus",       1569766873203998850),
        ("Stokçu / Karaborsacı",  1569766940359266445),
        ("Normal Çete Üyesi",     1573676328740458556),
    ],
    "Tarikat Çetesi": [
        ("Vaiz",                 1569767100921282671),
        ("Fedai",                1569767165685538886),
        ("İnisiye",              1569767215383842938),
        ("Tarikat Çete Üyesi",   1573676565429092482),
    ],
    "Milis Grubu": [
        ("Milis Birliği Üyesi", 1569768990371356805),
    ],
}

# Çete lider rolleri (kayıtta VERİLMEZ, çete onayında verilir)
CETE_LIDER_ROLLERI = {
    "Normal Çete":     1569766712860221641,  # 💀 • Çete Lideri
    "Tarikat Çetesi":  1569767025985851446,  # 🌑 • Mürşit
    "Milis Grubu":     1569768894531510424,  # 🛡️ • Milis Grubu Lideri
}

# Çete türüne göre "üye" rolü (kan bağı kesimi sırasında alınıp verilir)
CETE_UYE_ROLLERI = {
    "Normal Çete":     1573676328740458556,
    "Tarikat Çetesi":  1573676565429092482,
    "Milis Grubu":     1569768990371356805,
}

# ═══════════════════════════════════════════════════════════════════
# KRİTİK KANAL ID'LERİ
# ═══════════════════════════════════════════════════════════════════
# --- Kayıt ---
KANAL_KAYIT_SOHBET     = 1470543732913733726   # 💬・kayıt-sohbet
KANAL_KAYIT_LOG        = 1470746590175039620   # 🪪・kayıt-log
KANAL_KARAKTER_FORMU   = 1522022651642777891   # 📋・karakter-formu (forum)
KANAL_GIRIS_CIKIS      = 1568991063601840128   # 🚪・giriş-çıkış

# --- Bilgilendirme ---
KANAL_KURALLAR         = 1470751106714960109
KANAL_DUYURULAR        = 1470774288108884009
KANAL_GUNCELLEMELER    = 1470774969624428758
KANAL_BOT_GUNCELLEMESI = 1497904630644871188
KANAL_HAVA_DURUMU      = 1542660230641352869

# --- RP Bilgi kategorisi ---
KANAL_EVREN_VE_TARIHCE   = 1470775371904581694
KANAL_RP_KURALLARI       = 1470778314158510244
KANAL_HARITA_VE_ROTALAR  = 1480186194469060770
KANAL_RP_ROLLERI         = 1499662682133889044
KANAL_ARANANLAR          = 1541384930251251732
KANAL_RADYO_DUYURULARI   = 1568592836872372234
KANAL_SISTEMLER          = 1569701382699884675   # forum
KANAL_EVENT_DUYURULAR    = 1573687295670882364
KANAL_GENEL_TELSIZ_AGI   = 1573687456145080430
KANAL_KARABORSA_TAKAS    = 1573687496569524334
KANAL_ENFEKTE_BOLGELER   = 1573687525992697866

# --- Yönetim & Log (GİZLİ) ---
KANAL_ADMIN_LOG         = 1573680978805661796
KANAL_CETE_ONAY_LOG     = 1573681034699218954
KANAL_ENFEKSIYON_LOG    = 1573681090055512145
KANAL_ENVANTER_LOG      = 1573681142933094490
KANAL_EVENT_LOG         = 1573681197077368884

# --- Çete Yönetimi ---
KANAL_CETE_KURULUM_TALEPLERI = 1573682280533196931
KANAL_CETE_KURALLARI         = 1573682326347583488
KANAL_CETE_KASA_LOG          = 1573682420606304266
KANAL_BOLGE_SAVASLARI        = 1573682474226286703

# --- RP Dışı ---
KANAL_SOHBET            = 1470755295591399597
KANAL_FOTO_SOHBET       = 1470771325579563089
KANAL_BOT_KOMUT         = 1470771946596864223
KANAL_ANILAR            = 1470772176180346910
KANAL_SORU_VE_GORUSLER  = 1470772331411538133
KANAL_RP_ONERI          = 1470772673494909073
KANAL_ROL_DAVET         = 1518741650732748961
KANAL_BUMP              = 1571787432301428836

# ═══════════════════════════════════════════════════════════════════
# KATEGORİ ID'LERİ
# ═══════════════════════════════════════════════════════════════════
KATEGORI_HOSGELDIN           = 1470543732913733724
KATEGORI_BILGILENDIRME       = 1470754906104139829
KATEGORI_RP_BILGI            = 1470755022030770238
KATEGORI_RP_DISI             = 1480147052401791078
KATEGORI_EGLENCE             = 1480157572446294086
KATEGORI_PARTNERLIK          = 1518259273153384499
KATEGORI_YONETIM_LOG         = 1573680894861115412
KATEGORI_CETE_YONETIMI       = 1573682016518537346
KATEGORI_TEHLIKELI_BOLGELER  = 1568630383518556271
KATEGORI_SAHILER_IC_SU       = 1568631394723168449
KATEGORI_ANA_ULASIM          = 1568631624294211697
KATEGORI_KIRSAL_ALANLAR      = 1568631842007945406
KATEGORI_ASKERI_BOLGELER     = 1568632159109910658

# Şehir kategorileri (her şehir bir kategori, altında kanallar var)
KATEGORI_SEHIRLER = {
    "İstanbul": 1535978788826128444,
    "Bursa":    1535711581122601100,
    "Ankara":   1535721663034036415,
    "Konya":    1535978391680061520,
    "İzmir":    1535978454011347055,
    "Denizli":  1535978698677813378,
    "Antalya":  1535986009454415925,
    "Adana":    1535987190025298020,
    "Trabzon":  1568571608317300838,
    "Samsun":   1568571787262955540,
}

# Şehir lokal radyo kanalları (event yayınları için)
SEHIR_RADYO_KANALLARI = {
    "İstanbul": 1571238320078454915,
    "Ankara":   1568581122185629796,
    "İzmir":    1568583449885941860,
    "Konya":    1568588225746964620,
    "Antalya":  1568606232724504777,
    "Adana":    1568608126658154598,
    "Trabzon":  1568608874628513894,
    "Samsun":   1568584632021028986,
    "Denizli":  1568627384188670083,
    "Bursa":    1568627949731708998,
}

# Tüm RP kategorileri (lokasyon bazlı komutlar bu kategorilerde çalışır)
RP_KATEGORILERI = [
    *KATEGORI_SEHIRLER.values(),
    KATEGORI_TEHLIKELI_BOLGELER,
    KATEGORI_SAHILER_IC_SU,
    KATEGORI_ANA_ULASIM,
    KATEGORI_KIRSAL_ALANLAR,
    KATEGORI_ASKERI_BOLGELER,
]

# Kayıt komutunun çalıştığı kanallar (kayıt-sohbet veya bot-komut)
KAYIT_KANALLARI = {KANAL_KAYIT_SOHBET, KANAL_BOT_KOMUT}

# ═══════════════════════════════════════════════════════════════════
# EMOJİLER
# ═══════════════════════════════════════════════════════════════════
EMOJI_CAN          = "❤️"
EMOJI_ACLIK        = "🍖"
EMOJI_SUSUZLUK     = "💧"
EMOJI_PARA         = "🪙"
EMOJI_SLOT         = "🎒"
EMOJI_ENFEKSIYON   = "🦠"
EMOJI_CETE         = "🏴"
EMOJI_BASARI       = "✅"
EMOJI_HATA         = "❌"
EMOJI_UYARI        = "⚠️"
EMOJI_BILGI        = "ℹ️"
EMOJI_KILIT        = "🔒"
EMOJI_Olum         = "💀"
EMOJI_GOZLEMCİ     = "👁️"
EMOJI_ISIRIK       = "🦷"

# ═══════════════════════════════════════════════════════════════════
# EMBED RENKLERİ (Discord int)
# ═══════════════════════════════════════════════════════════════════
RENK_BASARI        = 0x57F287   # Yeşil
RENK_HATA          = 0xED4245   # Kırmızı
RENK_UYARI         = 0xFEE75C   # Sarı
RENK_BILGI         = 0x3498DB   # Mavi
RENK_PROFIL        = 0x9B59B6  # Mor
RENK_ENFEKSIYON    = 0x992B22  # Koyu kırmızı
RENK_CETE          = 0xE67E22  # Turuncu
RENK_KASA_YATIRMA  = 0x57F287  # Yeşil
RENK_KASA_CEKME    = 0xED4245  # Kırmızı
RENK_GOLGEMSI      = 0x2C2F33  # Koyu gri (genel embed arka planı)
RENK_Olum          = 0x1A1A1A  # Siyah

# ═══════════════════════════════════════════════════════════════════
# DİĞER
# ═══════════════════════════════════════════════════════════════════
DB_DOSYA_YOLU = "tlo_bot.db"

# Bot durumu (Discord presence)
BOT_DURUM_METNI = "TLOU Anadolu'yu izliyor 👁️"
BOT_DURUM_TIPI  = "watching"  # watching / playing / listening

# Versiyon
BOT_VERSIYON = "0.2.0"