"""
utils/formatting.py - Metin ve sure formatlama yardimcilari.
"""
from datetime import datetime, timezone, timedelta

TZ_ISTANBUL = timezone(timedelta(hours=3))


def format_sure(saniye: int) -> str:
    """Saniyeyi okunabilir sure formatina cevir.
    Ornek: 3600 -> '1 saat', 90000 -> '1 gun, 1 saat'
    """
    if saniye <= 0:
        return "0 dakika"
    gun = saniye // 86400
    saat = (saniye % 86400) // 3600
    dakika = (saniye % 3600) // 60
    parcalar = []
    if gun > 0:
        parcalar.append(f"{gun} gun")
    if saat > 0:
        parcalar.append(f"{saat} saat")
    if dakika > 0 and gun == 0:
        parcalar.append(f"{dakika} dakika")
    return ", ".join(parcalar) if parcalar else "1 dakikadan az"


def format_para(miktar: int) -> str:
    """Para miktarini emoji ile formatla."""
    return f"{miktar} 🪙"


def format_tarih(iso_tarih: str) -> str:
    """ISO tarih stringini okunabilir formata cevir.
    Ornek: '2026-11-22T15:30:00+03:00' -> '22 Kasim 2026, 15:30'
    """
    if not iso_tarih:
        return "Bilinmiyor"
    try:
        dt = datetime.fromisoformat(iso_tarih)
        aylar = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
                 "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]
        return f"{dt.day} {aylar[dt.month - 1]} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return iso_tarih


def kisalt(metin: str, max_len: int = 100) -> str:
    """Uzun metni kisalt ve '...' ekle."""
    if len(metin) <= max_len:
        return metin
    return metin[:max_len - 3] + "..."


def bar_olustur(deger: int, max_val: int = 100, uzunluk: int = 10,
                 dolu="█", bos="░") -> str:
    """Ilerleme cubugu olustur."""
    if max_val <= 0:
        return bos * uzunluk
    dolu_sayi = max(0, min(uzunluk, int((deger / max_val) * uzunluk)))
    return f"{dolu * dolu_sayi}{bos * (uzunluk - dolu_sayi)}"


def discord_timestamp(unix_ts: int, style: str = "R") -> str:
    """Discord'un goreli zaman damgasi olustur.
    style: 'R' (goreli - '5 dakika once'), 't' (kisa saat), 'T' (uzun saat),
           'd' (kisa tarih), 'D' (uzun tarih), 'F' (tarih + saat)
    """
    return f"<t:{unix_ts}:{style}>"


def sayi_formatla(n: int) -> str:
    """Buyuk sayilari binlik ayracla formatla (1.234.567)."""
    return f"{n:,}".replace(",", ".")
