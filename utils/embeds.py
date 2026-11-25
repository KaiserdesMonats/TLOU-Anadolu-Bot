"""
utils/embeds.py - Standart embed sablonlari
Tum cog'lar bu modulu import eder: from utils.embeds import *
"""
import discord
import config


def success_embed(title: str = "Basarili!", description: str = "") -> discord.Embed:
    """Yesil basari embed'i."""
    e = discord.Embed(
        title=f"{config.EMOJI_BASARI} {title}",
        description=description,
        color=config.RENK_BASARI
    )
    return e


def error_embed(title: str = "Hata!", description: str = "") -> discord.Embed:
    """Kirmizi hata embed'i."""
    e = discord.Embed(
        title=f"{config.EMOJI_HATA} {title}",
        description=description,
        color=config.RENK_HATA
    )
    return e


def warning_embed(title: str = "Dikkat!", description: str = "") -> discord.Embed:
    """Sari uyari embed'i."""
    e = discord.Embed(
        title=f"{config.EMOJI_UYARI} {title}",
        description=description,
        color=config.RENK_UYARI
    )
    return e


def info_embed(title: str = "Bilgi", description: str = "") -> discord.Embed:
    """Mavi bilgi embed'i."""
    e = discord.Embed(
        title=f"{config.EMOJI_BILGI} {title}",
        description=description,
        color=config.RENK_BILGI
    )
    return e


def profil_embed(user_data: dict, inventory: list = None,
                 gang: dict = None, enfeksiyon: dict = None,
                 slot_capacity: int = 0) -> discord.Embed:
    """Karakter profil karti."""
    isim = user_data.get('isim', 'Bilinmiyor')
    soyisim = user_data.get('soyisim', '')
    tam_isim = f"{isim} {soyisim}".strip() if soyisim else isim

    e = discord.Embed(
        title=f"🪪 Karakter Karta",
        description=f"**{tam_isim}**",
        color=config.RENK_PROFIL
    )

    # Yas, sehir, meslek
    yas = user_data.get('yas', '?')
    sehir = user_data.get('sehir', '?')
    meslek = user_data.get('meslek', '?')

    e.add_field(name="🌍 Sehir", value=sehir, inline=True)
    e.add_field(name="💼 Meslek", value=meslek, inline=True)
    e.add_field(name="🎂 Yas", value=str(yas) if yas else "?", inline=True)

    # Stats barlari
    can = user_data.get('can', 100)
    acluk = user_data.get('acluk', 100)
    susuzluk = user_data.get('susuzluk', 100)
    para = user_data.get('para', 0)

    def bar(deger, max_val=100, dolu_emoji="█", bos_emoji="░", uzunluk=10):
        dolu = max(0, min(uzunluk, int((deger / max_val) * uzunluk)))
        return f"{dolu_emoji * dolu}{bos_emoji * (uzunluk - dolu)}"

    e.add_field(
        name=f"{config.EMOJI_CAN} Can",
        value=f"`{bar(can)}` **{can}**/100",
        inline=False
    )
    e.add_field(
        name=f"{config.EMOJI_ACLIK} Aclik",
        value=f"`{bar(acluk)}` **{acluk}**/100",
        inline=False
    )
    e.add_field(
        name=f"{config.EMOJI_SUSUZLUK} Susuzluk",
        value=f"`{bar(susuzluk)}` **{susuzluk}**/100",
        inline=False
    )

    e.add_field(name=f"{config.EMOJI_PARA} Para", value=f"**{para}** 🪙", inline=True)
    e.add_field(name=f"{config.EMOJI_SLOT} Slot",
                value=f"**{len(inventory) if inventory else 0}**/{slot_capacity}",
                inline=True)

    # Enfeksiyon
    if enfeksiyon and enfeksiyon.get('var'):
        sev = enfeksiyon.get('seviye', 1)
        asama_ad = config.ENFEKSIYON_ASAMA_ISIMLERI.get(sev, "Bilinmiyor")
        kalan_saat = enfeksiyon.get('kalan_sure', 0) // 3600
        e.add_field(
            name=f"{config.EMOJI_ENFEKSIYON} Enfeksiyon",
            value=f"**{asama_ad}**\nKalan: ~{kalan_saat} saat",
            inline=False
        )
    else:
        e.add_field(
            name=f"{config.EMOJI_ENFEKSIYON} Enfeksiyon",
            value="✅ Temiz",
            inline=False
        )

    # Cete
    if gang:
        rol_goster = {"lider": "👑 Lider", "subay": "⚔️ Subay", "uye": "👤 Üye"}
        e.add_field(
            name=f"{config.EMOJI_CETE} Çete",
            value=f"**{gang.get('name', '?')}** ({gang.get('type', '?')})\n"
                  f"{rol_goster.get(gang.get('role', 'uye'), 'Üye')}",
            inline=False
        )

    # Envanter (varsa)
    if inventory:
        env_liste = "\n".join(f"• {i['item']} x{i['amount']}" for i in inventory[:10])
        if len(inventory) > 10:
            env_liste += f"\n... ve {len(inventory) - 10} esya daha"
        e.add_field(name=f"🎒 Envanter", value=env_liste, inline=False)
    else:
        e.add_field(name="🎒 Envanter", value="*Bos*", inline=False)

    return e


def cete_embed(gang_data: dict, members: list = None,
                inventory: list = None) -> discord.Embed:
    """Cete karti embed."""
    e = discord.Embed(
        title=f"🏴 Çete: {gang_data.get('name', '?')}",
        description=f"**Tür:** {gang_data.get('type', '?')}",
        color=config.RENK_CETE
    )

    e.add_field(name="💰 Kasa", value=f"**{gang_data.get('money', 0)}** 🪙", inline=True)
    e.add_field(name="👥 Üye", value=f"**{len(members) if members else 0}**", inline=True)

    # Yetenekler
    perks = gang_data.get('perks', [])
    if isinstance(perks, str):
        import json
        try:
            perks = json.loads(perks)
        except Exception:
            perks = []
    if perks:
        e.add_field(name="✨ Yetenekler", value="\n".join(f"• {p}" for p in perks),
                    inline=False)

    # Üyeler
    if members:
        rol_sira = {"lider": 0, "subay": 1, "uye": 2}
        sirali = sorted(members, key=lambda m: rol_sira.get(m.get('role', 'uye'), 3))
        uye_liste = []
        for m in sirali[:15]:
            rol_emoji = {"lider": "👑", "subay": "⚔️", "uye": "👤"}.get(m.get('role'), "👤")
            isim = f"{m.get('isim', '?')} {m.get('soyisim', '')}".strip()
            uye_liste.append(f"{rol_emoji} {isim}")
        e.add_field(name="👥 Üyeler", value="\n".join(uye_liste) or "Yok",
                    inline=False)

    # Kasa envanteri
    if inventory:
        env_liste = "\n".join(f"• {i['item']} x{i['amount']}" for i in inventory[:10])
        e.add_field(name="📦 Kasa Envanteri", value=env_liste, inline=False)

    return e


def log_embed(actor_name: str, action: str, details: str = "",
              color: int = None) -> discord.Embed:
    """Log kanallari icin embed."""
    e = discord.Embed(
        title=f"📝 Log: {action}",
        description=details,
        color=color or config.RENK_BILGI,
        timestamp=discord.utils.utcnow()
    )
    e.set_footer(text=f"Islemi yapan: {actor_name}")
    return e
