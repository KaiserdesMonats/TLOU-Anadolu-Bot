"""
utils/localization.py - Tüm şablon mesajlar burada.
Türkçe karakterler kullanılır (kayıt, başarılı, vb.).
Botun 'sesi' tutarlı olur, değişiklik kolay olur.
"""
# ==================================================================
# KAYIT SİSTEMİ
# ==================================================================
MSG_KAYIT_YETKISIZ = "Bu komutu kullanma yetkiniz yok. Sadece yetkililer kullanabilir."
MSG_KAYIT_YANLIS_KANAL = "Bu komut sadece `#kayıt-sohbet` kanalında kullanılabilir."
MSG_KAYIT_BASLATILDI = "Aşağıdan bir seçenek seçin: Gözlemci mi yoksa RP Oyuncusu mu?"
MSG_KAYIT_ZATEN_KAYITLI = "Zaten kayıtlısınız. Yeniden kayıt olmak için önce admin ile görüşün."
MSG_GOZLEMCI_BASARILI = "Gözlemci olarak kaydedildin. İyi eğlenceler!"
MSG_GOZLEMCI_ISIM_GEREKLI = "Lütfen bir isim girin."
MSG_RP_ADIM_SEHIR = "Aşağıdan şehrini seç:"
MSG_RP_ADIM_MESLEK = "Aşağıdan mesleğini seç:"
MSG_RP_ADIM_BILGI = "Bilgilerini gir ve tamamla:"
MSG_RP_YAS_HATA = "Yaş 15-80 arasında olmalı ve sayı olmalı."
MSG_RP_BASARILI = "RP Oyuncusu olarak kaydedildin! `/profil` komutunu kullanabilirsin."

# ==================================================================
# COOLDOWN
# ==================================================================
MSG_COOLDOWN_AKTIF = "Bu komut için {kalan_dk} dakika beklemelisin."
MSG_COOLDOWN_BEKLEME = "⏳ Bekleme süresi dolmadı."

# ==================================================================
# ENVANTER
# ==================================================================
MSG_ENVANTER_BOS = "Envanterin boş."
MSG_ENVANTER_DOLU = "Envanterin dolu! Slot geliştir veya eşya sat."
MSG_SLOT_MAX = "Maksimum slot seviyesine ulaştın."
MSG_SLOT_YETERSIZ_PARA = "Yetersiz para. Gereken: {cost} 🪙"
MSG_SLOT_BASARILI = "Slot geliştirildi! Yeni kapasite: {kapasite}"

# ==================================================================
# ENFEKSİYON
# ==================================================================
MSG_ISIRILDI = "🦷 {kullanici} tarafından ısırıldın! Enfeksiyon başladı."
MSG_ENFEKSIYON_ASAMA_ATLANDI = "🦠 Enfeksiyon ilerledi! Yeni aşama: {asama}"
MSG_ENFEKSIYON_OLUM = "💀 Enfeksiyon tamamlandı. Karakterin dönüşüm geçirdi."
MSG_DOKTOR_MUDAHALE = "⚕️ Doktor tarafından enfeksiyon süresi uzatıldı."
MSG_ASİ_URETILDI = "💉 Aşı üretildi! Enfeksiyon tamamen temizlendi."
MSG_ENFEKSIYON_TEMIZ = "✅ Enfeksiyon temiz."

# ==================================================================
# ÇETE
# ==================================================================
MSG_CETE_KURULUM_TALEP = "Çete kurulum talebin alındı. Admin onayı bekleniyor."
MSG_CETE_ONAYLANDI = "✅ Çeten onaylandı! Lider rolün verildi."
MSG_CETE_REDEDILDI = "❌ Çete talebin reddedildi. Sebep: {sebep}"
MSG_CETE_FESHEDILDI = "⚠️ Çeten feshedildi."
MSG_CETE_ZATEN_UYE = "Zaten bir çeteye üyesin. Önce ayrılman gerekir."
MSG_CETE_SINIR_DOLDU = "Bu türde maksimum çete sayısına ulaşıldı."
MSG_CETE_KASA_YATIRMA = "💰 {miktar} 🪙 kasaya yatırıldı."
MSG_CETE_KASA_CEKME = "💸 {miktar} 🪙 kasadan çekildi."
MSG_CETE_KASA_YETERSIZ = "Kasada yeterli para yok."
MSG_CETE_KASA_YETKISIZ = "Sadece lider ve subaylar para çekebilir."
MSG_CETE_DAVET_GONDERILDI = "Çete daveti gönderildi: {kullanici}"
MSG_CETE_KABUL_EDILDI = "Çeteye katıldın! Kan bağışı olarak {ucret} 🪙 kesildi."
MSG_CETE_KAN_BAGISI_YETERSIZ = "Çeteye katılmak için {ucret} 🪙 gerekir (kan bağışı)."
MSG_CETE_BASKIN_ILAN = "⚔️ {saldiran} çetesi {savunan} çetesine baskın ilan etti!"
MSG_CETE_BASKIN_HAZIRLIK = "Hazırlık süresi: {saat} saat. Savunmaya hazırlanın!"

# ==================================================================
# BÖLGE / YAĞMA
# ==================================================================
MSG_BOLGE_KILITLI = "🔒 Bu bölge şu an kilitli: {sebep}"
MSG_YAGMA_BASARILI = "Yağma başarılı! Kazanımlar: {kazanim}"
MSG_YAGMA_BASARISIZ = "Yağma sırasında bir şeyler ters gitti. Elde edilemedi."
MSG_ARASTIR_BASARILI = "Araştırma tamamlandı. Bulunanlar: {kazanim}"
MSG_ENFEKTE_TEMIZLENDI = "Enfekteler temizlendi. Kazanımlar: {kazanim}"

# ==================================================================
# EVENT
# ==================================================================
MSG_EVENT_KARGO = "📢 DİKKAT! Eski askeri bir Cargo uçağı {bolge} bölgesine acil durum ikmal kutusu bıraktı!"
MSG_EVENT_SURU = "⚠️ UYARI: {bolge} bölgesinde devasa bir enfekte sürüsü tespit edildi. Sessiz olun veya kaçın!"
MSG_EVENT_TUCCAR = "🛒 Gezici Tüccar {bolge} bölgesinde belirdi. Nadir eşyalar satışta!"
MSG_EVENT_RADYO = "📻 ...burası... güvenli bölge... tıbbi malzeme var... koordinatlar... {bolge}... yardım edin..."
MSG_EVENT_COOLDOWN = "Bu türde bir event yakın gerçekleşti. {kalan_gun} gün beklemelisin."

# ==================================================================
# ADMIN
# ==================================================================
MSG_ADMIN_IYILESTIR = "✅ {kullanici} iyileştirildi (Can/Açlık/Susuzluk %100)."
MSG_ADMIN_ENFEKSIYON_SIFIRLA = "✅ {kullanici} enfeksiyonu temizlendi."
MSG_ADMIN_ENVANTER_EKLE = "✅ {kullanici} kullanıcısına {esya} x{miktar} eklendi."
MSG_ADMIN_KARAKTER_SIFIRLA_ONAY = "⚠️ {kullanici} kullanıcısının tüm ilerlemesi silinecek. Onaylamak için 30 saniye içinde 'evet' yazın."
MSG_ADMIN_KARAKTER_SIFIRLA_IPTAL = "İşlem iptal edildi."
MSG_ADMIN_KARAKTER_SIFIRLA_BASARILI = "✅ {kullanici} karakteri sıfırlandı."
MSG_ADMIN_CETE_ONAYLA = "✅ Çete onaylandı: {isim}"
MSG_ADMIN_CETE_RED = "❌ Çete reddedildi: {isim}"
MSG_ADMIN_CETE_FESHET = "⚠️ Çete feshedildi: {isim}"
MSG_ADMIN_BOLGE_KILITLE = "🔒 Bölge kilitlendi: {sebep}"
MSG_ADMIN_BOLGE_ACILDI = "✅ Bölge kilidi açıldı."
MSG_ADMIN_LOG_YOK = "Bu türde kayıt bulunamadı."

# ==================================================================
# HATA MESAJLARI
# ==================================================================
MSG_KULLANICI_YOK = "Kullanıcı bulunamadı veya kayıtlı değil."
MSG_KARAKTER_OLUM = "💀 Karakterin ölü. Yeni karakter açmak için kayıt ol."
MSG_GOZLEMCİ_YETKISIZ = "Gözlemciler bu komutu kullanamaz."
MSG_KOMUT_BAKIMTA = "🔧 Bu komut şu an bakımda."
MSG_GENEL_HATA = "Bir hata oluştu. Lütfen tekrar deneyin veya yetkiliye başvurun."

# ==================================================================
# HAVA DURUMU
# ==================================================================
MSG_HAVA_GUNESLI = "☀️ Bugün hava güneşli. Normal koşullar geçerli."
MSG_HAVA_SIS = "🌫️ Bugün yoğun sis var. Araştırma/yağma başarısı %15 azaldı, gizlenme %20 arttı."
MSG_HAVA_YAGMUR = "🌧️ Bugün şiddetli yağmur var. Ateş yakmak zor, enfekte izleri siliniyor."
MSG_HAVA_SICAK = "🔥 Bugün aşırı sıcak. Susuzluk %20 daha hızlı düşer."

# ==================================================================
# YARDIM
# ==================================================================
MSG_YARDIM_BASLIK = "TLOU Anadolu - Komut Yardımı"
MSG_YARDIM_GIRIS = "Aşağıda tüm komutları kategorilere göre bulabilirsin."
