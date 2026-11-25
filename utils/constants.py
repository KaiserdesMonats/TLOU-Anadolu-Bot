"""
utils/constants.py - Oyun ici statik veriler.
Esya listeleri, hava durumu etkileri, meslek eylemleri, uretim tarifleri.
"""
from datetime import datetime, timezone, timedelta

TZ_ISTANBUL = timezone(timedelta(hours=3))


# ==================================================================
# ESYA LISTESI (envanter icin)
# ==================================================================
# Kategori: {esya_adi: aciklama}
ITEMS = {
    # Yiyecekler
    "Konserve Et":         {"kategori": "yiyecek", "satici_fiyat": 30, "tokluk": 25},
    "Ekmek":               {"kategori": "yiyecek", "satici_fiyat": 15, "tokluk": 15},
    "Meyve":               {"kategori": "yiyecek", "satici_fiyat": 20, "tokluk": 18},
    "Kurutulmus Et":       {"kategori": "yiyecek", "satici_fiyat": 40, "tokluk": 30},
    "Pismaniye":           {"kategori": "yiyecek", "satici_fiyat": 50, "tokluk": 35},
    # Icecekler
    "Su Sisesi":           {"kategori": "icecek", "satici_fiyat": 25, "susuzluk": 25},
    "Kirli Su":            {"kategori": "icecek", "satici_fiyat": 5,  "susuzluk": 10, "risk": 0.3},
    "Temizlenmis Su":      {"kategori": "icecek", "satici_fiyat": 30, "susuzluk": 30},
    "Cay":                 {"kategori": "icecek", "satici_fiyat": 35, "susuzluk": 20, "can": 5},
    # Tibbi
    "Kirli Sargi":         {"kategori": "medikal", "satici_fiyat": 20, "can": 10},
    "Temiz Sargi":         {"kategori": "medikal", "satici_fiyat": 50, "can": 25},
    "Antibiyotik":         {"kategori": "medikal", "satici_fiyat": 200, "ozel": True},
    "Agri Kesici":         {"kategori": "medikal", "satici_fiyat": 80, "can": 30},
    "Vitamin":             {"kategori": "medikal", "satici_fiyat": 60, "acluk": 10, "susuzluk": 5},
    "Asi":                 {"kategori": "medikal", "satici_fiyat": 0, "ozel": True},
    # Malzemeler
    "Tahta":               {"kategori": "malzeme", "satici_fiyat": 5},
    "Tohum":               {"kategori": "malzeme", "satici_fiyat": 5},
    "Metal Hurda":         {"kategori": "malzeme", "satici_fiyat": 10},
    "Kumas":               {"kategori": "malzeme", "satici_fiyat": 8},
    "Ip":                  {"kategori": "malzeme", "satici_fiyat": 12},
    "Plastik":             {"kategori": "malzeme", "satici_fiyat": 7},
    "Cam Kırığı":          {"kategori": "malzeme", "satici_fiyat": 3},
    "Pil":                 {"kategori": "malzeme", "satici_fiyat": 25},
    "Civata":              {"kategori": "malzeme", "satici_fiyat": 4},
    # Silah parcalari
    "Bicak Sapi":          {"kategori": "silah_parca", "satici_fiyat": 30},
    "Namlu":               {"kategori": "silah_parca", "satici_fiyat": 100},
    "Tetik Mekanizması":   {"kategori": "silah_parca", "satici_fiyat": 80},
    "Sarjor":              {"kategori": "silah_parca", "satici_fiyat": 60},
    # Silahlar
    "Sopalı Bıcak":        {"kategori": "silah", "satici_fiyat": 50,  "hasar": 15},
    "Av Bıçağı":           {"kategori": "silah", "satici_fiyat": 120, "hasar": 25},
    "Tabanca":             {"kategori": "silah", "satici_fiyat": 500, "hasar": 40},
    "Tüfek":               {"kategori": "silah", "satici_fiyat": 1500,"hasar": 75},
    # Mühimmat
    "9mm Mermi":           {"kategori": "mhimmat", "satici_fiyat": 15},
    "Tüfek Mermisi":       {"kategori": "mhimmat", "satici_fiyat": 30},
    # Asi bilesenleri (cok nadir)
    "Mantar Spor Ornegi":  {"kategori": "asi_bilesen", "satici_fiyat": 0, "ozel": True},
    "Kulturel Mantar":     {"kategori": "asi_bilesen", "satici_fiyat": 0, "ozel": True},
    "Steril Bidon":        {"kategori": "asi_bilesen", "satici_fiyat": 0, "ozel": True},
    "Enfekte Kan Ornegi":  {"kategori": "asi_bilesen", "satici_fiyat": 0, "ozel": True},
    "Kimyasal Bilesik":    {"kategori": "asi_bilesen", "satici_fiyat": 0, "ozel": True},
    # Diger
    "Ellenmis Cikmak":     {"kategori": "diger", "satici_fiyat": 70, "can": 50},
    "Ceset Cantasi":       {"kategori": "diger", "satici_fiyat": 40, "slot": 5},
}

# ==================================================================
# HAVA DURUMU ETKILERI
# ==================================================================
HAVA_DURUMLARI = {
    "gunesli": {
        "isim": "Gunesli",
        "emoji": "☀️",
        "aciklama": "Normal kosullar gecerli.",
        "etkiler": {}
    },
    "sisli": {
        "isim": "Yogun Sis",
        "emoji": "🌫️",
        "aciklama": "Arastirma/yagma basari sansi %15 azaldi. Gizlenme %20 artti.",
        "etkiler": {
            "yagma_basari": -0.15,
            "arastir_basari": -0.15,
            "gizlen_basari": +0.20,
        }
    },
    "yagmurlu": {
        "isim": "Siddetli Yagmur",
        "emoji": "🌧️",
        "aciklama": "Ates yakmak zor. Enfekte izleri siliniyor (takip edilmesi zor).",
        "etkiler": {
            "ates_yakmak": False,
            "iz_temizleme": True,
        }
    },
    "asiri_sicak": {
        "isim": "Asiri Sicak",
        "emoji": "🔥",
        "aciklama": "Susuzluk %20 daha hizli duser.",
        "etkiler": {
            "susuzluk_dusus_carpani": 1.20,
        }
    },
}

# ==================================================================
# MESLEK EYLEMLERI
# ==================================================================
# Her meslek grubu icin eylemler: {isim: {beklenti, kazanim, risk}}
MESLEK_EYLEMLERI = {
    "Ciftci": [
        {
            "isim": "Tarlayı Sulat",
            "beklenti": "Suyu mantarli topraga verir, ekin sagligi artar.",
            "kazanim": {"item": "Tohum", "miktar": 1},
            "risk": 0.0,
            "cooldown": "meslek"
        },
        {
            "isim": "Hasat Yap",
            "beklenti": "Olgun ekinleri toplar.",
            "kazanim": {"item": "Ekmek", "miktar": 2},
            "risk": 0.1,
            "cooldown": "meslek"
        },
        {
            "isim": "Tohum Ek",
            "beklenti": "Topraga tohum eker.",
            "kazanim": {"para": 20},
            "risk": 0.0,
            "cooldown": "meslek"
        },
    ],
    "Doktor": [
        {
            "isim": "İlk Yardım Yap",
            "beklenti": "Hasta birine ilk yardim yapar.",
            "kazanim": {"para": 50},
            "risk": 0.05,
            "cooldown": "meslek"
        },
        {
            "isim": "Ameliyat Yap",
            "beklenti": "Cerrahi mudahale.",
            "kazanim": {"para": 200},
            "risk": 0.2,
            "cooldown": "meslek"
        },
        {
            "isim": "Aşı Araştır",
            "beklenti": "Asi bileseni arastirir.",
            "kazanim": {"item_rastgele": "asi_bilesen"},
            "risk": 0.5,
            "cooldown": "meslek"
        },
    ],
    "Tamirci": [
        {
            "isim": "Araç Tamir Et",
            "beklenti": "Bozuk bir araci tamir eder.",
            "kazanim": {"para": 80},
            "risk": 0.1,
            "cooldown": "meslek"
        },
        {
            "isim": "Jeneratör Kur",
            "beklenti": "Bir bolgeye jenerator kurar.",
            "kazanim": {"para": 150},
            "risk": 0.15,
            "cooldown": "meslek"
        },
        {
            "isim": "Silah Bakımı Yap",
            "beklenti": "Silahlari bakima alir.",
            "kazanim": {"para": 60},
            "risk": 0.05,
            "cooldown": "meslek"
        },
    ],
    "Polis": [
        {
            "isim": "Devriye Gez",
            "beklenti": "Bolgeyi devriye gezer.",
            "kazanim": {"para": 50},
            "risk": 0.15,
            "cooldown": "meslek"
        },
        {
            "isim": "Kontrol Noktası Kur",
            "beklenti": "Kontrol noktasi kurar.",
            "kazanim": {"para": 70},
            "risk": 0.1,
            "cooldown": "meslek"
        },
    ],
    "Valilik": [
        {
            "isim": "Halkla İlişkiler",
            "beklenti": "Halk ile gorusur.",
            "kazanim": {"para": 100},
            "risk": 0.0,
            "cooldown": "meslek"
        },
        {
            "isim": "Tahsis Yap",
            "beklenti": "Kaynak tahsis eder.",
            "kazanim": {"para": 150},
            "risk": 0.05,
            "cooldown": "meslek"
        },
    ],
    "Askeri": [
        {
            "isim": "Devriye",
            "beklenti": "Bolge devriyesi.",
            "kazanim": {"para": 80},
            "risk": 0.2,
            "cooldown": "meslek"
        },
        {
            "isim": "Keşif Görevi",
            "beklenti": "Keşfe cikar.",
            "kazanim": {"para": 120},
            "risk": 0.25,
            "cooldown": "meslek"
        },
    ],
}

# ==================================================================
# URETIM TARIFLERI
# ==================================================================
# {urun: {malzemeler: {esya: miktar}, sonuc_miktar: int}}
URETIM_TARIFLERI = {
    "Sopalı Bıcak": {
        "malzemeler": {"Tahta": 1, "Kumas": 1, "Cam Kırığı": 1},
        "sonuc_miktar": 1,
    },
    "Kirli Sargi": {
        "malzemeler": {"Kumas": 2},
        "sonuc_miktar": 1,
    },
    "Ellenmis Cikmak": {
        "malzemeler": {"Metal Hurda": 3, "Pil": 1},
        "sonuc_miktar": 1,
    },
    "Temizlenmis Su": {
        "malzemeler": {"Kirli Su": 2, "Kumas": 1},
        "sonuc_miktar": 1,
    },
}

# ==================================================================
# YAGMA / ARASTIRMA KAZANIM TABLOSU
# ==================================================================
# Her kategori icin olasi kazanmlar ve olasiliklari
YAGMA_KAZANIMLAR = {
    "yagma": [
        {"item": "Metal Hurda", "miktar": 1, "sans": 0.30},
        {"item": "Tahta", "miktar": 2, "sans": 0.25},
        {"item": "Kumas", "miktar": 1, "sans": 0.20},
        {"item": "Konserve Et", "miktar": 1, "sans": 0.10},
        {"item": "Kirli Sargi", "miktar": 1, "sans": 0.08},
        {"item": "Pil", "miktar": 1, "sans": 0.05},
        {"item": "9mm Mermi", "miktar": 2, "sans": 0.02},
    ],
    "arastir": [
        {"item": "Ip", "miktar": 1, "sans": 0.25},
        {"item": "Plastik", "miktar": 2, "sans": 0.20},
        {"item": "Civata", "miktar": 3, "sans": 0.20},
        {"item": "Vitamin", "miktar": 1, "sans": 0.10},
        {"item": "Ellenmis Cikmak", "miktar": 1, "sans": 0.05},
        {"item": "Bicak Sapi", "miktar": 1, "sans": 0.03},
        {"item": "Enfekte Kan Ornegi", "miktar": 1, "sans": 0.02},
    ],
    "enfekte_temizle": [
        {"item": "Enfekte Kan Ornegi", "miktar": 1, "sans": 0.15},
        {"item": "Antibiyotik", "miktar": 1, "sans": 0.05},
        {"item": "Kirli Sargi", "miktar": 2, "sans": 0.30},
        {"item": "Para", "miktar": 30, "sans": 0.50},
    ],
}

# Para kazanma sansi (direkt para)
YAGMA_PARA_SANSI = {
    "yagma": (0.3, (10, 50)),     # %30 sans, 10-50 arasi
    "arastir": (0.2, (5, 30)),
    "enfekte_temizle": (0.4, (20, 80)),
}

# ==================================================================
# CETE PERK LISTESI
# ==================================================================
CETE_PERKLERI = {
    "gizli_depo":         {"isim": "Gizli Depo",
                            "aciklama": "Çete uyeleri icin ortak envanter kapasitesi +5 slot artar."},
    "yerel_ag":           {"isim": "Yerel Ağ",
                            "aciklama": "Kendi bolgesinde /arastir ve /yagma cooldown 15 dk azalir."},
    "kara_borsa":         {"isim": "Kara Borsa Bağlantısı",
                            "aciklama": "Çete kasa esyasi satildiginda %10 fazla para alinir."},
    "gozdagi":            {"isim": "Gözdağı",
                            "aciklama": "Bolge savasi kazaninca kaybedenin pasif geliri 24 saat yarim iner."},
    "kacak_yollar":       {"isim": "Kaçak Yollar",
                            "aciklama": "Baskasi kontrol ettigi bolgede haraca yakalanma sansi %15 azalir."},
    "geri_donusum":       {"isim": "Geri Dönüşüm",
                            "aciklama": "Çete uyeleri /uretim yaparken malzeme ihtiyaci %10 azalir."},
    "sadakat_bagi":       {"isim": "Sadakat Bağı",
                            "aciklama": "Yeni uyelerden alinan kan bagisi %20 dusuk olur."},
    "sokak_ilk_yardim":   {"isim": "Sokak İlk Yardımı (Normal Çete Özel)",
                            "aciklama": "Çete uyeleri kayit olurken ekstra 1 Kirli Sargi baslar."},
    "kor_inanc":          {"isim": "Kör İnanç (Tarikat Özel)",
                            "aciklama": "/rituel ile enfeksiyon ilerleme hizi %10 yavasar (iyilestirmez)."},
}

# ==================================================================
# EVENT KAZANIM TABLOLARI (Kargo, Tuccar vb.)
# ==================================================================
EVENT_KARGO_ICERIK = [
    {"item": "Antibiyotik", "miktar": 2},
    {"item": "9mm Mermi", "miktar": 10},
    {"item": "Temizlenmis Su", "miktar": 5},
    {"item": "Temiz Sargı", "miktar": 3},
    {"item": "Vitamin", "miktar": 3},
]

# Asiya gitmesi gereken bilesenler (1 asi icin 5 farkli)
ASI_BILESENLERI = [
    "Mantar Spor Ornegi",
    "Kulturel Mantar",
    "Steril Bidon",
    "Enfekte Kan Ornegi",
    "Kimyasal Bilesik",
]
