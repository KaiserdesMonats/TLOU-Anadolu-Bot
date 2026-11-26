"""
cogs/uretim.py - Uretim Sistemi
Hybrid komutlar: /uretim, /uretim-tarifler
Envanterdeki malzemelerle yeni esya uretir.
Cete perk "Geri Donusum" aktifse malzeme ihtiyaci %10 azalir.
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import URETIM_TARIFLERI, ITEMS
from utils.formatting import format_para
from utils.localization import (
    MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ, MSG_ENVANTER_DOLU,
)


logger = logging.getLogger("tlo.cogs.uretim")


# ==================================================================
# TARIF VIEW (Dropdown)
# ==================================================================
class UretimDropdown(discord.ui.Select):
    """Uretim tarifi secim dropdown'i."""

    def __init__(self, user_data: dict, kullanici_cetesi: dict = None,
                 owner_id: int = None):
        self.user_data = user_data
        self.kullanici_cetesi = kullanici_cetesi
        self.owner_id = owner_id

        options = []
        for tarif_adi, tarif in URETIM_TARIFLERI.items():
            malzeme_listesi = []
            for malzeme, miktar in tarif['malzemeler'].items():
                # Cete perk "geri_donusum" varsa %10 azalt
                gerekli = miktar
                if kullanici_cetesi and 'perks' in kullanici_cetesi:
                    perks = kullanici_cetesi['perks']
                    if isinstance(perks, list) and 'geri_donusum' in perks:
                        gerekli = max(1, int(miktar * 0.9))
                malzeme_listesi.append(f"{malzeme} x{gerekli}")
            aciklama = " + ".join(malzeme_listesi)
            if len(aciklama) > 100:
                aciklama = aciklama[:97] + "..."
            options.append(discord.SelectOption(
                label=f"{tarif_adi} (x{tarif['sonuc_miktar']})",
                value=tarif_adi,
                description=aciklama
            ))
        super().__init__(
            placeholder='Uretmek istedigin tarifi sec...',
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Hata", "Bu menüyü yalnızca başlatan kullanıcı kullanabilir."
                ),
                ephemeral=True
            )
            return

        secim = self.values[0]
        tarif = URETIM_TARIFLERI.get(secim)
        if not tarif:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Tarif bulunamadi."),
                ephemeral=True
            )
            return

        # Once tum malzemeler var mi kontrol et
        user_id = interaction.user.id
        eksikler = []
        silinecek = []
        for malzeme, miktar in tarif['malzemeler'].items():
            gerekli = miktar
            if self.kullanici_cetesi and 'perks' in self.kullanici_cetesi:
                perks = self.kullanici_cetesi['perks']
                if isinstance(perks, list) and 'geri_donusum' in perks:
                    gerekli = max(1, int(miktar * 0.9))
            sahip = await db.has_item(user_id, malzeme, gerekli)
            if not sahip:
                mevcut = 0
                env = await db.get_inventory(user_id)
                for e in env:
                    if e['item'] == malzeme:
                        mevcut = e['amount']
                        break
                eksikler.append(f"{malzeme} (gerekli: {gerekli}, sahip: {mevcut})")
            else:
                silinecek.append((malzeme, gerekli))

        if eksikler:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Eksik Malzeme",
                    f"**{secim}** uretmek icin eksik malzemeler:\n"
                    + "\n".join(f"• {e}" for e in eksikler)
                ),
                ephemeral=True
            )
            return

        # Slot doluluk kontrolu
        slot_kapasite = await db.get_slot_capacity(user_id)
        envanter_adet = await db.get_inventory_count(user_id)
        kullanilacak_miktar = sum(miktar for _, miktar in silinecek)
        sonuc_envanter_adet = (
            envanter_adet - kullanilacak_miktar + tarif['sonuc_miktar']
        )
        if sonuc_envanter_adet > slot_kapasite:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Envanter Dolu",
                    MSG_ENVANTER_DOLU
                ),
                ephemeral=True
            )
            return

        # Malzemeleri sil
        for malzeme, miktar in silinecek:
            await db.remove_item(user_id, malzeme, miktar)

        # Urunu ekle
        await db.add_item(user_id, secim, tarif['sonuc_miktar'])

        # Log
        await db.add_action_log('envanter', user_id, None,
                                 'uretim',
                                 {'tarif': secim,
                                  'malzemeler': silinecek,
                                  'urun': secim,
                                  'miktar': tarif['sonuc_miktar']})

        # Basari mesaji
        embed = embeds.success_embed(
            "Uretim Basarili",
            f"**{secim}** x{tarif['sonuc_miktar']} uretildi!\n\n"
            f"**Kullanilan malzemeler:**\n"
            + "\n".join(f"• {m} x{miktar}" for m, miktar in silinecek)
        )

        # Cete perk bilgisi
        if (self.kullanici_cetesi and 'perks' in self.kullanici_cetesi and
            isinstance(self.kullanici_cetesi['perks'], list) and
            'geri_donusum' in self.kullanici_cetesi['perks']):
            embed.add_field(
                name="♻️ Geri Donusum Perki",
                value=f"Cetenizin **Geri Donusum** perki sayesinde "
                      f"malzeme ihtiyaciniz %10 azaldi.",
                inline=False
            )

        await interaction.response.edit_message(view=None)
        await interaction.followup.send(embed=embed)


class UretimView(discord.ui.View):
    """Uretim dropdown view."""
    def __init__(self, user_data: dict, kullanici_cetesi: dict = None,
                 owner_id: int = None):
        super().__init__(timeout=120)
        self.add_item(UretimDropdown(user_data, kullanici_cetesi, owner_id))


# ==================================================================
# COG SINIFI
# ==================================================================
class UretimCog(commands.Cog):
    """Uretim sistemi cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /uretim
    # ==================================================================
    @commands.hybrid_command(
        name="uretim",
        description="Envanterdeki malzemelerle esya uretir"
    )
    async def uretim_slash(self, ctx: commands.Context):
        """Uretim menusunu gosterir."""
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

        # Cete bilgisini al (perk kontrolu icin)
        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if kullanici_cetesi:
            kullanici_cetesi = (
                await db.get_gang_by_id(kullanici_cetesi['gang_id'])
                or kullanici_cetesi
            )

        # Tarif listesi embed'i
        embed = discord.Embed(
            title="🔨 Uretim Menusu",
            description=(
                f"{ctx.author.mention}, asagidan uretmek istedigin "
                f"tarifi sec.\n\n"
                f"**Kurallar:**\n"
                f"• Uretim icin malzemeler envanterinde olmali\n"
                f"• Uretim sonrasi malzemeler silinir\n"
                f"• Cete perk **Geri Donusum** varsa malzeme %10 azalir"
            ),
            color=config.RENK_BILGI
        )

        # Tarif listesi
        tarif_metin = []
        for tarif_adi, tarif in URETIM_TARIFLERI.items():
            malzemeler = []
            for malzeme, miktar in tarif['malzemeler'].items():
                gerekli = miktar
                if (kullanici_cetesi and 'perks' in kullanici_cetesi and
                    isinstance(kullanici_cetesi['perks'], list) and
                    'geri_donusum' in kullanici_cetesi['perks']):
                    gerekli = max(1, int(miktar * 0.9))
                malzemeler.append(f"{malzeme} x{gerekli}")
            tarif_metin.append(
                f"**{tarif_adi}** (x{tarif['sonuc_miktar']}): " +
                " + ".join(malzemeler)
            )

        embed.add_field(
            name="📋 Mevcut Tarifler",
            value="\n".join(tarif_metin),
            inline=False
        )

        # Cete perk bilgisi
        if (kullanici_cetesi and 'perks' in kullanici_cetesi and
            isinstance(kullanici_cetesi['perks'], list) and
            'geri_donusum' in kullanici_cetesi['perks']):
            embed.add_field(
                name="♻️ Geri Donusum Perki Aktif",
                value=f"Ceteniz **{kullanici_cetesi.get('name', '?')}** "
                      f"tarafindan secilen bu perki sayesinde "
                      f"malzeme ihtiyaciniz %10 azaldi.",
                inline=False
            )

        view = UretimView(user_data, kullanici_cetesi, ctx.author.id)
        await self._send(ctx, embed=embed, view=view)

    # ==================================================================
    # /uretim-tarifler
    # ==================================================================
    @commands.hybrid_command(
        name="uretim-tarifler",
        description="Tum uretim tariflerini gosterir"
    )
    async def uretim_tarifler_slash(self, ctx: commands.Context):
        """Tum tarifleri listeler."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        embed = discord.Embed(
            title="📋 Uretim Tarifleri",
            description=f"Toplam {len(URETIM_TARIFLERI)} tarif mevcut.",
            color=config.RENK_BILGI
        )

        for tarif_adi, tarif in URETIM_TARIFLERI.items():
            malzemeler = []
            for malzeme, miktar in tarif['malzemeler'].items():
                malzemeler.append(f"{malzeme} x{miktar}")
            embed.add_field(
                name=f"🔨 {tarif_adi} (x{tarif['sonuc_miktar']})",
                value=" + ".join(malzemeler),
                inline=False
            )

        embed.set_footer(text="Cete 'Geri Donusum' perki malzeme ihtiyacini %10 azaltir.")
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
    await bot.add_cog(UretimCog(bot))
    logger.info("UretimCog yuklendi")
