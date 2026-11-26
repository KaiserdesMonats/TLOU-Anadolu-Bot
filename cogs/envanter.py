"""
cogs/envanter.py - Envanter Sistemi
Hybrid komutlar: /envanter, /slot-gelistir
Kullanici esyalarini goruntuler ve slot kapasitesini gelistirir.
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.checks import is_kayitli
from utils.constants import ITEMS
from utils.formatting import format_para
from utils.localization import (
    MSG_ENVANTER_BOS, MSG_SLOT_MAX, MSG_SLOT_YETERSIZ_PARA,
    MSG_SLOT_BASARILI, MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
)


logger = logging.getLogger("tlo.cogs.envanter")


class EnvanterCog(commands.Cog):
    """Envanter ve slot gelistirme cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /envanter
    # ==================================================================
    @commands.hybrid_command(
        name="envanter",
        description="Karakter envanterini gosterir"
    )
    async def envanter_slash(self, ctx: commands.Context):
        """Kullanici envanterini gosterir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        # Gozlemciler envanter goremez
        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        # Olu karakter kontrolu
        if user_data.get('is_dead', 0):
            await self._send_error(ctx,
                "💀 Karakterin olu. Bu komutu kullanamazsin."
            )
            return

        inventory = await db.get_inventory(ctx.author.id)
        slot_capacity = await db.get_slot_capacity(ctx.author.id)

        # Embed olustur
        embed = discord.Embed(
            title=f"🎒 Envanter - {user_data.get('isim', '?')}",
            color=config.RENK_BILGI
        )

        # Slot doluluk
        toplam_esya = sum(i['amount'] for i in inventory) if inventory else 0
        doluluk_yuzde = int((toplam_esya / slot_capacity) * 100) if slot_capacity > 0 else 0

        embed.add_field(
            name="📊 Slot Doluluk",
            value=f"**{toplam_esya}** / {slot_capacity} "
                  f"({doluluk_yuzde}%)",
            inline=False
        )

        # Slot seviye gosterimi
        sev = user_data.get('slot_seviye', 0)
        seviye_adlari = ["Baslangic (10)", "1. Seviye (15)",
                         "2. Seviye (20)", "3. Seviye (25)", "4. Seviye (30)"]
        seviye_ad = seviye_adlari[sev] if sev < len(seviye_adlari) else "MAX"
        embed.add_field(name="📈 Slot Seviye", value=seviye_ad, inline=True)

        # Para
        embed.add_field(name="💰 Para",
                        value=format_para(user_data.get('para', 0)),
                        inline=True)

        # Envanter icerigi
        if not inventory:
            embed.add_field(
                name="📦 Esyalar",
                value=f"*{MSG_ENVANTER_BOS}*",
                inline=False
            )
        else:
            # Esyalari kategoriye gore grupla
            kategoriler = {}
            for item in inventory:
                isim = item['item']
                miktar = item['amount']
                # Kategori bul
                kategori = "Diger"
                if isim in ITEMS:
                    kategori = ITEMS[isim].get('kategori', 'Diger')
                # Kategori adlarini Turkcelestir
                kat_ad = {
                    'yiyecek': '🍽️ Yiyecekler',
                    'icecek': '🥤 Icecekler',
                    'medikal': '⚕️ Tibbi',
                    'malzeme': '🧰 Malzemeler',
                    'silah_parca': '🔩 Silah Parcalari',
                    'silah': '🔫 Silahlar',
                    'mhimmat': '⚪ Muhimmat',
                    'asi_bilesen': '🧪 Asi Bilesenleri',
                    'diger': '📦 Diger',
                }.get(kategori, '📦 Diger')

                if kat_ad not in kategoriler:
                    kategoriler[kat_ad] = []
                kategoriler[kat_ad].append(f"• {isim} x{miktar}")

            # Her kategori icin field ekle (25 field sinirina dikkat)
            fields_added = 0
            for kat_ad, liste in kategoriler.items():
                if fields_added >= 20:
                    break
                icerik = "\n".join(liste[:10])
                if len(liste) > 10:
                    icerik += f"\n... ve {len(liste) - 10} esya daha"
                embed.add_field(name=kat_ad, value=icerik, inline=True)
                fields_added += 1

        embed.set_footer(text=f"User ID: {ctx.author.id}")
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /slot-gelistir
    # ==================================================================
    @commands.hybrid_command(
        name="slot-gelistir",
        description="Envanter slot kapasitesini para ile gelistirir"
    )
    async def slot_gelistir_slash(self, ctx: commands.Context):
        """Slot kapasitesini 1 seviye gelistirir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        # Gozlemciler slot gelistiremez
        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        # Olu karakter kontrolu
        if user_data.get('is_dead', 0):
            await self._send_error(ctx,
                "💀 Karakterin olu. Bu komutu kullanamazsin."
            )
            return

        # Mevcut seviye
        sev = user_data.get('slot_seviye', 0)
        if sev >= len(config.SLOT_GELISTIRME_SEVIYELERI):
            await self._send_error(ctx, MSG_SLOT_MAX)
            return

        # Maliyet
        cost = config.SLOT_GELISTIRME_SEVIYELERI[sev][1]
        yeni_kapasite = config.SLOT_GELISTIRME_SEVIYELERI[sev][0]

        # Para kontrolu
        if user_data['para'] < cost:
            await self._send_error(ctx,
                MSG_SLOT_YETERSIZ_PARA.format(cost=cost)
            )
            return

        # Gelistir
        success, message, cost = await db.upgrade_slot(ctx.author.id)
        if not success:
            await self._send_error(ctx, message)
            return

        # Basari mesaji
        embed = embeds.success_embed(
            "Slot Gelistirildi!",
            f"{MSG_SLOT_BASARILI.format(kapasite=yeni_kapasite)}\n"
            f"Harcanan: {format_para(cost)}\n"
            f"Yeni Seviye: {sev + 1}/4"
        )

        # Sonraki seviye bilgilendirmesi
        if sev + 1 < len(config.SLOT_GELISTIRME_SEVIYELERI):
            sonraki_cost = config.SLOT_GELISTIRME_SEVIYELERI[sev + 1][1]
            sonraki_kapasite = config.SLOT_GELISTIRME_SEVIYELERI[sev + 1][0]
            embed.add_field(
                name="📈 Sonraki Seviye",
                value=f"Kapasite: {sonraki_kapasite} slot\n"
                      f"Maliyet: {format_para(sonraki_cost)}",
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 Tebrikler!",
                value="Maksimum slot seviyesine ulastin!",
                inline=False
            )

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /esya-bilgi (bonus komut)
    # ==================================================================
    @commands.hybrid_command(
        name="esya-bilgi",
        description="Bir esyanin detaylarini gosterir"
    )
    @app_commands.describe(
        esya="Bilgi alinacak esya adi"
    )
    async def esya_bilgi_slash(self, ctx: commands.Context, esya: str):
        """Bir esyanin detaylarini gosterir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data or user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        # Esya listede var mi?
        # Eslesen esyayi bul (case-insensitive)
        esya_bulundu = None
        for isim, detay in ITEMS.items():
            if isim.lower() == esya.lower():
                esya_bulundu = (isim, detay)
                break

        if not esya_bulundu:
            await self._send_error(ctx,
                f"'{esya}' adli esya bulunamadi. "
                f"Toplam {len(ITEMS)} esya var."
            )
            return

        isim, detay = esya_bulundu
        embed = discord.Embed(
            title=f"📦 {isim}",
            color=config.RENK_BILGI
        )

        # Kategori
        kategori = detay.get('kategori', 'diger')
        kat_ad = {
            'yiyecek': '🍽️ Yiyecek',
            'icecek': '🥤 Icecek',
            'medikal': '⚕️ Tibbi',
            'malzeme': '🧰 Malzeme',
            'silah_parca': '🔩 Silah Parcasi',
            'silah': '🔫 Silah',
            'mhimmat': '⚪ Muhimmat',
            'asi_bilesen': '🧪 Asi Bileseni',
            'diger': '📦 Diger',
        }.get(kategori, kategori)
        embed.add_field(name="Kategori", value=kat_ad, inline=True)

        # Satici fiyati
        satici_fiyat = detay.get('satici_fiyat', 0)
        embed.add_field(name="💰 Satici Fiyati",
                        value=format_para(satici_fiyat), inline=True)

        # Ozel mi?
        if detay.get('ozel'):
            embed.add_field(name="⚠️ Ozel",
                            value="Evet - Nadir esya", inline=True)

        # Etkileri
        etkiler = []
        if 'can' in detay:
            etkiler.append(f"❤️ Can +{detay['can']}")
        if 'acluk' in detay:
            etkiler.append(f"🍖 Acluk +{detay['acluk']}")
        if 'susuzluk' in detay:
            etkiler.append(f"💧 Susuzluk +{detay['susuzluk']}")
        if 'tokluk' in detay:
            etkiler.append(f"🍖 Tokluk +{detay['tokluk']}")
        if 'hasar' in detay:
            etkiler.append(f"⚔️ Hasar {detay['hasar']}")
        if 'slot' in detay:
            etkiler.append(f"🎒 Ekstra Slot +{detay['slot']}")
        if 'risk' in detay:
            yuzde = int(detay['risk'] * 100)
            etkiler.append(f"⚠️ Enfeksiyon Riski %{yuzde}")

        if etkiler:
            embed.add_field(name="✨ Etkiler",
                            value="\n".join(etkiler), inline=False)
        else:
            embed.add_field(name="✨ Etkiler",
                            value="*Ozel etkisi yok*", inline=False)

        # Kullanicinin bu esyadan kac tane var?
        envanter = await db.get_inventory(ctx.author.id)
        sahip_oldugu = next(
            (i['amount'] for i in envanter if i['item'] == isim), 0
        )
        embed.add_field(name="📊 Senin Envanterinde",
                        value=f"**{sahip_oldugu}** adet", inline=True)

        embed.set_footer(text=f"User ID: {ctx.author.id}")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # YARDIMCI FONKSIYON
    # ==================================================================
    async def _send(self, ctx: commands.Context, embed=None, content=None,
                     view=None, ephemeral=True):
        """Prefix/slash farkı gözetmeksizin mesaj gönder.
        'uygulama cevap vermedi' hatasını önler.
        """
        try:
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    if content:
                        await ctx.interaction.followup.send(content, embed=embed, view=view, ephemeral=ephemeral)
                    else:
                        await ctx.interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    if content:
                        await ctx.interaction.response.send_message(content, embed=embed, view=view, ephemeral=ephemeral)
                    else:
                        await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)
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

    async def _send_error(self, ctx: commands.Context, message: str):
        """Prefix/slash farki gectirimeden hata mesaji gonder.
        'uygulama cevap vermedi' hatasini onler.
        """
        embed = embeds.error_embed("Hata", message)
        try:
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await self._send(ctx, embed=embed)
        except Exception as e:
            logger.error(f"Mesaj gonderme hatasi: {e}")
            try:
                await self._send(ctx, embed=embed)
            except Exception:
                pass



# ==================================================================
# SETUP
# ==================================================================
async def setup(bot: commands.Bot):
    await bot.add_cog(EnvanterCog(bot))
    logger.info("EnvanterCog yuklendi")
