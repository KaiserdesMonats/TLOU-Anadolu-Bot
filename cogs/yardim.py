"""
cogs/yardim.py - Yardim Menusu
Komut: /yardim [kategori]
Tum komutlari kategorilere gore listeler.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import embeds


logger = logging.getLogger("tlo.cogs.yardim")


# ==================================================================
# KOMUT KATEGORILERI
# ==================================================================
KOMUT_KATEGORILERI = {
    "kayit": {
        "isim": "Kayit Sistemi",
        "emoji": "🚪",
        "aciklama": "Karakter kaydi ve olusturma komutlari",
        "komutlar": [
            (
                "/kayit [@kullanici]",
                "Yeni uye kaydi (yetkili)",
                "Kayit Yetkilisi, RP Yetkilisi, Admin",
            ),
        ],
    },
    "karakter": {
        "isim": "Karakter",
        "emoji": "🪪",
        "aciklama": "Karakter bilgileri ve istatistikler",
        "komutlar": [
            ("/profil [@kullanici]", "Karakter profil kartini gosterir", "Herkes"),
            ("/envanter", "Karakter envanterini gosterir", "RP Oyuncusu"),
            (
                "/esya-bilgi <esya>",
                "Esya detaylarini gosterir (oneri listesi var)",
                "RP Oyuncusu",
            ),
            (
                "/kullan <esya> [miktar]",
                "Tuketilebilir esya kullan (yemek/icecek/sargi)",
                "RP Oyuncusu",
            ),
            (
                "/takas @hedef <verilecek> <istenen> [miktarlar]",
                "Oyuncu ile esya takasi teklif et",
                "RP Oyuncusu",
            ),
            ("/slot-gelistir", "Envanter slot kapasitesini artirir", "RP Oyuncusu"),
        ],
    },
    "meslek": {
        "isim": "Meslek & Eylemler",
        "emoji": "💼",
        "aciklama": "Meslek eylemleri ve yankesicilik",
        "komutlar": [
            ("/meslek", "Meslek eylemlerini gosterir (1 saat CD)", "RP Oyuncusu"),
            ("/yankesicilik @hedef", "Gizlice esya calma (2 saat CD)", "Çete üyesi"),
        ],
    },
    "hayatta_kalma": {
        "isim": "Hayatta Kalma",
        "emoji": "⚔️",
        "aciklama": "Yagma, arastirma, enfekte temizleme (3 saat global CD)",
        "komutlar": [
            ("/yagma", "Bulundugun bolgeyi yagmala", "RP Oyuncusu"),
            ("/arastir", "Bolgeyi arastir, malzeme bul", "RP Oyuncusu"),
            ("/enfekte-temizle", "Bolgedeki enfekteleri temizle", "RP Oyuncusu"),
            ("/uretim", "Malzemelerle esya uret", "RP Oyuncusu"),
            ("/uretim-tarifler", "Tum uretim tariflerini goster", "RP Oyuncusu"),
        ],
    },
    "enfeksiyon": {
        "isim": "Enfeksiyon",
        "emoji": "🦠",
        "aciklama": "Enfeksiyon durumu, doktor mudahalesi, asi",
        "komutlar": [
            ("/enfeksiyon", "Enfeksiyon durumunu gosterir", "RP Oyuncusu"),
            (
                "/doktor-mudahale @hedef",
                "Enfeksiyon suresini uzatir (+4 saat)",
                "Doktor",
            ),
            ("/asi-uret", "5 bilesenle asi uretir", "Bashekim/Cerrah"),
            ("/asi-uygula @hedef", "Hastayi iyilestirir", "Bashekim/Cerrah"),
            (
                "/rituel",
                "Tarikat ritueli, ilerlemeyi yavaslatabilir",
                "Tarikat (Kör Inanc perki)",
            ),
        ],
    },
    "cete": {
        "isim": "Çete Sistemi",
        "emoji": "🏴",
        "aciklama": "Çete kurma, kasa, bolge, baskin",
        "komutlar": [
            ("/cete-kur <isim> <tur>", "Çete kurma talebi", "RP Oyuncusu"),
            ("/cete-bilgi [cete_adi]", "Çete bilgilerini gosterir", "RP Oyuncusu"),
            ("/cete-kasa", "Çete kasa bakiyesi", "Çete üyesi"),
            ("/cete-yatir <miktar>", "Kasaya para yatir", "Çete üyesi"),
            ("/cete-cek <miktar>", "Kasadan para cek", "Lider/Subay"),
            ("/cete-davet @hedef", "Çeteye üye davet et", "Lider/Subay"),
            ("/cete-ayril", "Çeteden ayril (lider hariç)", "Çete üyesi"),
            ("/cete-bolge-al", "Bulundugun bolgeyi kontrol altina al", "Lider/Subay"),
            (
                "/cete-harac",
                "Uyelerin harac seviyelerini goster",
                "Çete üyesi",
            ),
            (
                "/cete-harac-ayarla @uye <0-3>",
                "Uyenin harac seviyesini ayarla",
                "Lider/Subay",
            ),
            ("/cete-baskin <cete> <kanal>", "Baskın ilan et", "Lider"),
            ("/cete-perkler", "Tüm yetenekleri listele", "Herkes"),
        ],
    },
    "event": {
        "isim": "Eventler",
        "emoji": "📡",
        "aciklama": "Kargo, sürü, tüccar, radyo sinyali eventleri",
        "komutlar": [
            ("/event-bilgi", "Event türleri hakkinda bilgi", "Herkes"),
            ("/event-aktifler", "Aktif eventleri listeler", "Herkes"),
            ("/event-baslat <tur> <kanal>", "Event baslatir", "RP Yetkilisi/Admin"),
        ],
    },
    "hava": {
        "isim": "Hava Durumu",
        "emoji": "🌦️",
        "aciklama": "Hava durumu bilgisi ve geçmisi",
        "komutlar": [
            ("/hava-durumu", "Su anki hava durumunu gosterir", "Herkes"),
            ("/hava-durumu-gecmisi [limit]", "Son hava durumu kayitlari", "Herkes"),
        ],
    },
    "admin": {
        "isim": "Admin & Yonetim",
        "emoji": "🛡️",
        "aciklama": "Admin komutlari (gizli log'lar)",
        "komutlar": [
            ("/admin-iyilestir @hedef", "Can/acluk/susuzluk %100", "Admin"),
            ("/admin-enfeksiyon-sifirla @hedef", "Enfeksiyonu temizle", "Admin"),
            (
                "/admin-envanter-ekle @hedef <esya> [miktar]",
                "Envantere esya ekle",
                "Admin",
            ),
            (
                "/admin-karakter-sifirla @hedef",
                "Karakteri sifirla (2 asamali onay)",
                "Admin",
            ),
            ("/admin-canlandir @hedef", "Olu karakteri geri getir", "Admin"),
            ("/karakter-incele @hedef", "Tüm verileri goster (God Eye)", "Admin"),
            ("/log-cek <tur> [limit]", "Log kayitlarini getir", "Admin"),
            ("/bolge-kilitle <kanal> <sebep>", "Bolgeyi kilitle", "RP Yetkilisi/Admin"),
            ("/bolge-ac <kanal>", "Bolge kilidini ac", "RP Yetkilisi/Admin"),
            ("/cete-onayla <id/isim>", "Çete talebini onayla", "Admin"),
            ("/cete-reddet <id/isim> <sebep>", "Çete talebini reddet", "Admin"),
            ("/cete-feshet <id/isim> [sebep]", "Çete feshet", "Admin"),
            (
                "/hava-durumu-degistir <durum>",
                "Hava durumunu degistir",
                "RP Yetkilisi/Admin",
            ),
            ("/isirit @hedef <siddet>", "Bir kisiyi enfekte et", "RP Yetkilisi/Admin"),
        ],
    },
    "diger": {
        "isim": "Diger",
        "emoji": "📦",
        "aciklama": "Yardim ve bilgi komutlari",
        "komutlar": [
            ("/yardim [kategori]", "Bu yardim menusu", "Herkes"),
        ],
    },
}


# ==================================================================
# COG SINIFI
# ==================================================================
class YardimCog(commands.Cog):
    """Yardim menusu cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /yardim
    # ==================================================================
    @commands.hybrid_command(
        name="yardim", description="Tüm komutları kategorilere göre listeler"
    )
    @app_commands.describe(
        kategori="Belirli bir kategorinin detaylarını göster (opsiyonel)"
    )
    @app_commands.choices(
        kategori=[
            app_commands.Choice(name="🚪 Kayıt Sistemi", value="kayit"),
            app_commands.Choice(name="🪪 Karakter", value="karakter"),
            app_commands.Choice(name="💼 Meslek & Eylemler", value="meslek"),
            app_commands.Choice(name="⚔️ Hayatta Kalma", value="hayatta_kalma"),
            app_commands.Choice(name="🦠 Enfeksiyon", value="enfeksiyon"),
            app_commands.Choice(name="🏴 Çete Sistemi", value="cete"),
            app_commands.Choice(name="📡 Eventler", value="event"),
            app_commands.Choice(name="🌦️ Hava Durumu", value="hava"),
            app_commands.Choice(name="🛡️ Admin & Yönetim", value="admin"),
            app_commands.Choice(name="📦 Diğer", value="diger"),
        ]
    )
    async def yardim_slash(
        self, ctx: commands.Context, kategori=None
    ):
        """Yardım menüsü. Prefix ve slash uyumlu."""
        # kategori parametresi:
        # - Slash: app_commands.Choice objesi (kategori.value string)
        # - Prefix: string (ya da None)
        # - Hybrid prefix ile Choice geçmez, direkt string gelir
        if kategori is not None:
            if hasattr(kategori, 'value'):
                kat_key = kategori.value
            else:
                kat_key = str(kategori)
        else:
            kat_key = None

        if kat_key:
            # Belirli kategori detayı
            kat = KOMUT_KATEGORILERI.get(kat_key)
            if not kat:
                await self._send(ctx, embeds.error_embed(
                    "Hata", f"Kategori bulunamadı: {kat_key}"
                ))
                return

            embed = discord.Embed(
                title=f"{kat['emoji']} {kat['isim']}",
                description=kat["aciklama"],
                color=config.RENK_BILGI,
            )

            for komut, aciklama, yetki in kat["komutlar"]:
                embed.add_field(
                    name=f" `{komut}`",
                    value=f"{aciklama}\n**Yetki:** {yetki}",
                    inline=False,
                )

            embed.set_footer(text=f"TLOU Anadolu | Toplam {len(kat['komutlar'])} komut")
            await self._send(ctx, embed=embed)
            return

        # Tüm kategorileri özet olarak göster
        embed = discord.Embed(
            title="📚 TLOU Anadolu - Yardım Menüsü",
            description=(
                f"Prefix: `{config.PREFIX}` veya `/` (slash)\n\n"
                f"Aşağıdaki kategorilerden birini seçerek detaylı bilgi alabilirsin:\n"
                f"Örnek: `/yardim cete` veya `/yardim enfeksiyon`"
            ),
            color=config.RENK_BILGI,
        )

        toplam_komut = 0
        for kat_key, kat in KOMUT_KATEGORILERI.items():
            komut_sayisi = len(kat["komutlar"])
            toplam_komut += komut_sayisi
            embed.add_field(
                name=f"{kat['emoji']} {kat['isim']}",
                value=f"{kat['aciklama']}\n`/yardim {kat_key}` ({komut_sayisi} komut)",
                inline=False,
            )

        embed.set_footer(
            text=f"TLOU Anadolu • Toplam {toplam_komut} komut • Versiyon {config.BOT_VERSIYON}"
        )
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /hakkinda (bonus komut)
    # ==================================================================
    @commands.hybrid_command(name="hakkinda", description="Bot hakkında bilgi gösterir")
    async def hakkinda_slash(self, ctx: commands.Context):
        """Bot hakkinda bilgi."""
        embed = discord.Embed(
            title="🧟‍♂️ TLOU Anadolu",
            description=(
                "Modern Türkiye'de geçen, The Last of Us (TLOU) tarzı "
                "mantar/zombi kıyameti sonrası hayatta kalma RP sunucusu.\n\n"
                f"**Versiyon:** {config.BOT_VERSIYON}\n"
                f"**Prefix:** `{config.PREFIX}` veya `/` (slash)\n"
                f"**Zaman Ölçeği:** 1 gerçek gün = 1 RP günü\n"
                f"**Ölüm Sistemi:** Permadeath (kalıcı ölüm)"
            ),
            color=config.RENK_BILGI,
        )

        embed.add_field(
            name="📋 Temel Özellikler",
            value=(
                "• Kayıt sistemi (Gözlemci / RP Oyuncusu)\n"
                "• 10 şehir, çok sayıda meslek\n"
                "• Çete sistemi (kasa, bölge, baskın, 9 perk)\n"
                "• 4 aşamalı enfeksiyon + aşı üretimi\n"
                "• Hayatta kalma (açlık, susuzluk, can)\n"
                "• Event sistemi (kargo, sürü, tüccar, radyo)\n"
                "• Günlük hava durumu + oyun etkileri\n"
                "• Permadeath + 3 günlük karantina\n"
                "• Detaylı admin araçları ve log sistemi"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔗 Faydalı Kanallar",
            value=(
                f"• <#{config.KANAL_KURALLAR}> - Kurallar\n"
                f"• <#{config.KANAL_RP_KURALLARI}> - RP kurallari\n"
                f"• <#{config.KANAL_RP_ROLLERI}> - Roller\n"
                f"• <#{config.KANAL_HARITA_VE_ROTALAR}> - Harita\n"
                f"• <#{config.KANAL_HAVA_DURUMU}> - Hava durumu"
            ),
            inline=False,
        )

        embed.set_footer(text="TLOU Anadolu | Discord bot | discord.py")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /komutlar (bonus - kisaca tum komut listesi)
    # ==================================================================
    @commands.hybrid_command(
        name="komutlar", description="Tüm komutları kısaca listeler"
    )
    async def komutlar_slash(self, ctx: commands.Context):
        """Kisa komut listesi."""
        embed = discord.Embed(
            title="📋 Tüm Komutlar",
            description=f"Prefix: `{config.PREFIX}` veya `/` (slash)",
            color=config.RENK_BILGI,
        )

        for kat_key, kat in KOMUT_KATEGORILERI.items():
            if not kat["komutlar"]:
                continue
            komut_listesi = "\n".join(f"• `{k[0]}`" for k in kat["komutlar"])
            embed.add_field(
                name=f"{kat['emoji']} {kat['isim']} ({len(kat['komutlar'])})",
                value=komut_listesi,
                inline=True,
            )

        embed.set_footer(text="Detaylı bilgi için: /yardim [kategori]")
        await self._send(ctx, embed=embed)

    async def _send(self, ctx: commands.Context, embed=None, content=None, view=None):
        """Prefix/slash farkı gözetmeksizin mesaj gönder.
        'uygulama cevap vermedi' hatasını önler.
        """
        try:
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    if content:
                        await ctx.interaction.followup.send(content, embed=embed, view=view)
                    else:
                        await ctx.interaction.followup.send(embed=embed, view=view)
                else:
                    if content:
                        await ctx.interaction.response.send_message(content, embed=embed, view=view)
                    else:
                        await ctx.interaction.response.send_message(embed=embed, view=view)
            else:
                if content:
                    await ctx.send(content, embed=embed, view=view)
                else:
                    await ctx.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Mesaj gönderme hatası: {e}")
            try:
                if content:
                    await ctx.send(content, embed=embed, view=view)
                else:
                    await ctx.send(embed=embed, view=view)
            except Exception:
                pass


# ==================================================================
# SETUP
# ==================================================================
async def setup(bot: commands.Bot):
    await bot.add_cog(YardimCog(bot))
    logger.info("YardimCog yuklendi")
