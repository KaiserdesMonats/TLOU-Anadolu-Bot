"""
cogs/takas.py - Oyuncular Arasi Takas Sistemi (v0.2.0 - YENI)
Komut: /takas @hedef verecegin_esya istedigin_esya [miktarlar]

Ornek: /takas @Ahmet verecegin_esya:"Kirli Sargi" istedigin_esya:"Ekmek"
       verecegin_miktar:2 istedigin_miktar:3

Akis:
1. Teklif eden esyalarini ve hedefin esyalarini kontrol eder.
2. Teklif HERKESE ACIK bir mesajla hedefe gosterilir (Kabul/Red butonlari).
3. Hedef kabul ederse esyalar iki tarafta da bir daha kontrol edilip
   envanterler arasinda degistirilir ve ikisine de log dusulur.
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import esya_bul, esya_onerileri
from utils.formatting import format_para
from utils.localization import MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ


logger = logging.getLogger("tlo.cogs.takas")


class TakasView(discord.ui.View):
    """Takas teklifi kabul/red view'i (hedefe gosterilir)."""

    def __init__(self, hedef: discord.Member, teklif: dict):
        super().__init__(timeout=180)
        self.hedef = hedef
        self.teklif = teklif
        self.sonuc = None

    @discord.ui.button(label="Kabul Et", emoji="✅",
                       style=discord.ButtonStyle.success)
    async def kabul_btn(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True
            )
            return
        self.sonuc = 'kabul'
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Reddet", emoji="❌",
                       style=discord.ButtonStyle.danger)
    async def red_btn(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True
            )
            return
        self.sonuc = 'red'
        self.stop()
        await interaction.response.edit_message(view=None)


class TakasCog(commands.Cog):
    """Oyuncular arasi takas cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # ORTAK DOGRULAMA
    # ------------------------------------------------------------------
    async def _takas_dogrula(self, veren_id: int, veren_isim: str,
                             veren_miktar: int, isteyen_id: int,
                             istenen_isim: str, istenen_miktar: int) -> str:
        """Takasin yapilabilir olup olmadigini kontrol eder.
        Hata mesaji dondurur (yoksa None). Teklif ve kabul aninda kullanilir.
        """
        # Esyalari cozumle (Turkce toleransli)
        ver_bulundu = esya_bul(veren_isim)
        ist_bulundu = esya_bul(istenen_isim)
        if not ver_bulundu:
            return f"'{veren_isim}' adli esya bulunamadi."
        if not ist_bulundu:
            return f"'{istenen_isim}' adli esya bulunamadi."
        ver_isim, _ = ver_bulundu
        ist_isim, _ = ist_bulundu

        if ver_isim == ist_isim:
            return "Ayni esyayi kendi kendine takas edemezsin."

        # Veren tarafin envanteri
        veren_envanter = await db.get_inventory(veren_id)
        veren_sahip = sum(
            i['amount'] for i in veren_envanter
            if i['item'] == ver_isim
        )
        if veren_sahip < veren_miktar:
            return (f"Teklif edenin **{ver_isim}** x{veren_miktar} yok "
                    f"(envanterinde {veren_sahip} adet var).")

        # Isteyen tarafin envanteri
        isteyen_envanter = await db.get_inventory(isteyen_id)
        isteyen_sahip = sum(
            i['amount'] for i in isteyen_envanter
            if i['item'] == ist_isim
        )
        if isteyen_sahip < istenen_miktar:
            return (f"Hedefin **{ist_isim}** x{istenen_miktar} yok "
                    f"(envanterinde {isteyen_sahip} adet var).")

        # Slot kapasitesi (takas sonrasi doluluk)
        veren_kapasite = await db.get_slot_capacity(veren_id)
        veren_adet = await db.get_inventory_count(veren_id)
        veren_sonra = veren_adet - veren_miktar + istenen_miktar
        if veren_sonra > veren_kapasite:
            return (f"Teklif edenin envanteri takas sonrasi dolacak "
                    f"({veren_sonra}/{veren_kapasite} slot).")

        isteyen_kapasite = await db.get_slot_capacity(isteyen_id)
        isteyen_adet = await db.get_inventory_count(isteyen_id)
        isteyen_sonra = isteyen_adet - istenen_miktar + veren_miktar
        if isteyen_sonra > isteyen_kapasite:
            return (f"Hedefin envanteri takas sonrasi dolacak "
                    f"({isteyen_sonra}/{isteyen_kapasite} slot).")

        return None

    # ==================================================================
    # /takas
    # ==================================================================
    @commands.hybrid_command(
        name="takas",
        description="Bir oyuncu ile esya takasi teklif eder"
    )
    @app_commands.describe(
        hedef="Takas yapacagin oyuncu",
        verecegin_esya="Hedefe verecegin esya (yazarken oneriler cikar)",
        istedigin_esya="Hedeften istedigin esya (yazarken oneriler cikar)",
        verecegin_miktar="Verecegin esya adedi (varsayilan: 1)",
        istedigin_miktar="Istedigin esya adedi (varsayilan: 1)",
    )
    async def takas_slash(self, ctx: commands.Context, hedef: discord.Member,
                          verecegin_esya: str, istedigin_esya: str,
                          verecegin_miktar: int = 1,
                          istedigin_miktar: int = 1):
        """Esya takasi teklifi gonderir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return
        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return
        if user_data.get('is_dead', 0):
            await self._send_error(ctx,
                "💀 Karakterin olu. Bu komutu kullanamazsin."
            )
            return

        if hedef.id == ctx.author.id:
            await self._send_error(ctx, "Kendinle takas yapamazsin.")
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx,
                f"{hedef.mention} kayitli bir oyuncu degil.")
            return
        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx,
                "Gozlemciler takas yapamaz.")
            return
        if hedef_data.get('is_dead', 0):
            await self._send_error(ctx,
                f"{hedef.mention} adli karakterin olu, takas yapamaz."
            )
            return

        if verecegin_miktar <= 0 or istedigin_miktar <= 0:
            await self._send_error(ctx,
                "Miktarlar 1'den kucuk olamaz.")
            return

        # On dogrulama
        hata = await self._takas_dogrula(
            ctx.author.id, verecegin_esya, verecegin_miktar,
            hedef.id, istedigin_esya, istedigin_miktar
        )
        if hata:
            await self._send_error(ctx, hata)
            return

        ver_isim = esya_bul(verecegin_esya)[0]
        ist_isim = esya_bul(istedigin_esya)[0]

        teklif = {
            'veren_id': ctx.author.id,
            'veren_isim': ctx.author.display_name,
            'veren_mention': ctx.author.mention,
            'hedef_id': hedef.id,
            'hedef_mention': hedef.mention,
            'verilen_esya': ver_isim,
            'verilen_miktar': verecegin_miktar,
            'istenen_esya': ist_isim,
            'istenen_miktar': istedigin_miktar,
        }

        # Teklifi goster (HERKESE ACIK - hedef tiklayabilmeli)
        embed = discord.Embed(
            title="🤝 Takas Teklifi",
            description=(
                f"{hedef.mention}, {ctx.author.mention} sana bir takas "
                f"teklif etti!\n\n"
                f"**Teklif eden verir:** {ver_isim} x{verecegin_miktar}\n"
                f"**Teklif eden ister:** {ist_isim} x{istedigin_miktar}"
            ),
            color=config.RENK_BILGI
        )
        embed.set_footer(text="180 saniye icinde yanit ver.")

        view = TakasView(hedef, teklif)
        await self._send(ctx, content=hedef.mention, embed=embed, view=view,
                         ephemeral=False)

        await view.wait()

        if view.sonuc != 'kabul':
            if view.sonuc == 'red':
                sonuc_metni = f"{hedef.mention} takas teklifini reddetti."
            else:
                sonuc_metni = (
                    f"{hedef.mention} sure icinde yanit vermedi, "
                    f"takas iptal edildi."
                )
            await self._send(ctx, ephemeral=False,
                embed=embeds.warning_embed("Takas Iptal", sonuc_metni)
            )
            return

        # ----------------------------------------------------------
        # KABUL: Tekrar dogrula (bekleme suresinde envanterler
        # degismis olabilir), sonra guvenli sekilde esya degistir.
        # ----------------------------------------------------------
        try:
            hata = await self._takas_dogrula(
                ctx.author.id, ver_isim, verecegin_miktar,
                hedef.id, ist_isim, istedigin_miktar
            )
            if hata:
                await self._send(ctx, ephemeral=False,
                    embed=embeds.error_embed(
                        "Takas Gerceklesemedi", hata
                    )
                )
                return

            # Esyalari cikar (once ikisi de cikarilir, sonra eklenir)
            ok_veren = await db.remove_item(
                ctx.author.id, ver_isim, verecegin_miktar
            )
            if not ok_veren:
                await self._send(ctx, ephemeral=False,
                    embed=embeds.error_embed(
                        "Takas Gerceklesemedi",
                        f"{ctx.author.mention} adli oyuncunun "
                        f"{ver_isim} esyasi arada gitti."
                    )
                )
                return

            ok_hedef = await db.remove_item(
                hedef.id, ist_isim, istedigin_miktar
            )
            if not ok_hedef:
                # Verenin esyasini geri ver
                await db.add_item(ctx.author.id, ver_isim, verecegin_miktar)
                await self._send(ctx, ephemeral=False,
                    embed=embeds.error_embed(
                        "Takas Gerceklesemedi",
                        f"{hedef.mention} adli oyuncunun "
                        f"{ist_isim} esyasi arada gitti."
                    )
                )
                return

            # Esyalari ver
            await db.add_item(hedef.id, ver_isim, verecegin_miktar)
            await db.add_item(ctx.author.id, ist_isim, istedigin_miktar)

            # Loglar (her iki taraf)
            takas_detay = {
                'veren': ctx.author.id,
                'hedef': hedef.id,
                'verilen': {'esya': ver_isim, 'miktar': verecegin_miktar},
                'istenen': {'esya': ist_isim, 'miktar': istedigin_miktar},
            }
            try:
                await db.add_action_log(
                    'takas', ctx.author.id, hedef.id, 'takas', takas_detay
                )
            except Exception as e:
                logger.error(f"takas log hatasi: {e}")

            # Envanter log kanali
            if ctx.guild:
                env_log = ctx.guild.get_channel(config.KANAL_ENVANTER_LOG)
                if env_log:
                    log_embed = discord.Embed(
                        title="🤝 Takas Gerceklesti",
                        description=(
                            f"**{ctx.author.mention}** -> "
                            f"**{hedef.mention}**\n"
                            f"Giden: {ver_isim} x{verecegin_miktar}\n"
                            f"Gelen: {ist_isim} x{istedigin_miktar}"
                        ),
                        color=config.RENK_BILGI,
                        timestamp=discord.utils.utcnow()
                    )
                    try:
                        await env_log.send(embed=log_embed)
                    except Exception:
                        pass

            await self._send(ctx, ephemeral=False,
                embed=embeds.success_embed(
                    "Takas Tamamlandi",
                    f"{ctx.author.mention} <-> {hedef.mention}\n"
                    f"{ver_isim} x{verecegin_miktar} <-> "
                    f"{ist_isim} x{istedigin_miktar}"
                )
            )
        except Exception as e:
            logger.error(f"takas kabul akisi hatasi: {e}", exc_info=True)
            await self._send(ctx, ephemeral=False,
                embed=embeds.error_embed(
                    "Hata",
                    "Takas sirasinda beklenmeyen bir hata olustu. "
                    "Envanter durumu icin /envanter komutunu kullan."
                )
            )

    # Autocomplete: verilecek esya
    @takas_slash.autocomplete("verecegin_esya")
    async def takas_verilen_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        return [
            app_commands.Choice(name=name, value=name)
            for name in esya_onerileri(current)
        ]

    # Autocomplete: istenen esya
    @takas_slash.autocomplete("istedigin_esya")
    async def takas_istenen_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        return [
            app_commands.Choice(name=name, value=name)
            for name in esya_onerileri(current)
        ]

    # ==================================================================
    # YARDIMCI FONKSIYONLAR
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
        """Prefix/slash farki gectirimeden hata mesaji gonder."""
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
    await bot.add_cog(TakasCog(bot))
    logger.info("TakasCog yuklendi")
