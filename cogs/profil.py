"""
cogs/profil.py - Karakter Profil Karti
Hybrid komut: /profil ve tlo.profil
Kullanici kendi veya baskasinin profilini goruntuleyebilir.
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.checks import is_kayitli, is_gozlemci
from utils.localization import MSG_KULLANICI_YOK


logger = logging.getLogger("tlo.cogs.profil")


class ProfilCog(commands.Cog):
    """Profil karti goruntuleme cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="profil",
        description="Karakter profilini gosterir"
    )
    @app_commands.describe(
        kullanici="Profilini gormek istedigin kisi (bos = kendin)"
    )
    async def profil_slash(self, ctx: commands.Context,
                          kullanici: discord.Member = None):
        """Profil karti gosterir."""
        # Hedef kullanici: parametre verilmisse o, yoksa komutu yazan
        hedef = kullanici if kullanici else ctx.author

        # Veritabanindan kullanici verisi
        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        # Olu karakter kontrolu
        if user_data.get('is_dead', 0):
            await self._send_error(ctx,
                f"💀 {hedef.mention} karakteri olu. "
                f"Yeni karakter acmak icin kayit olun."
            )
            return

        # Gozlemci profili (sade, sadece isim)
        if user_data.get('gozlemci', 0):
            embed = discord.Embed(
                title="👁️ Gozlemci Profili",
                description=f"**{user_data.get('isim', 'Gozlemci')}**",
                color=config.RENK_BILGI
            )
            embed.add_field(
                name="Durum",
                value="Gozlemci - RP'ye katilmiyor",
                inline=False
            )
            embed.set_footer(text=f"User ID: {hedef.id}")
            if hedef.display_avatar:
                embed.set_thumbnail(url=hedef.display_avatar.url)
            await self._send(ctx, embed=embed)
            return

        # RP Oyuncusu profili - tum verileri topla
        inventory = await db.get_inventory(hedef.id)
        gang = await db.get_user_gang(hedef.id)
        enfeksiyon = await db.get_enfeksiyon_durumu(hedef.id)
        slot_capacity = await db.get_slot_capacity(hedef.id)

        # Profil embed'i
        embed = embeds.profil_embed(
            user_data=user_data,
            inventory=inventory,
            gang=gang,
            enfeksiyon=enfeksiyon,
            slot_capacity=slot_capacity
        )

        # Avatar
        if hedef.display_avatar:
            embed.set_thumbnail(url=hedef.display_avatar.url)

        # Kayit tarihi
        kayit_tarihi = user_data.get('kayit_tarihi')
        if kayit_tarihi:
            from utils.formatting import format_tarih
            embed.set_footer(
                text=f"User ID: {hedef.id} | Kayit: {format_tarih(kayit_tarihi)}"
            )
        else:
            embed.set_footer(text=f"User ID: {hedef.id}")

        await self._send(ctx, embed=embed)

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
    await bot.add_cog(ProfilCog(bot))
    logger.info("ProfilCog yuklendi")
