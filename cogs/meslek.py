"""
cogs/meslek.py - Meslek Sistemi
Hybrid komutlar: /meslek
Meslek eylemleri, cooldown'lar, yankesicilik mekaniği.
"""
import logging
import random
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import MESLEK_EYLEMLERI, ITEMS, YAGMA_KAZANIMLAR
from utils.formatting import format_sure, format_para
from utils.localization import (
    MSG_COOLDOWN_AKTIF, MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
    MSG_GENEL_HATA,
)


logger = logging.getLogger("tlo.cogs.meslek")


# ==================================================================
# MESLEK GRUBU ESPRISI
# ==================================================================
# Kayit sirasinda "meslek_label" olarak kaydedilir. Cog meslegi tespit
# etmek icin kullanici rolune veya user_data.meslek alanina bakar.
# Meslek grubunu tespit etmek icin bir yardimci fonksiyon:
def meslek_grubu_bul(meslek_label: str) -> str:
    """Meslek adindan meslek grubunu bul.
    Ornek: 'Tarla Iscisi' -> 'Ciftci'
    """
    for grup, roller in config.MESLEK_GRUPLARI.items():
        for label, _ in roller:
            if label == meslek_label:
                return _grup_isim_donustur(grup)
    # Eslesme yoksa, basit kontrol
    meslek_lower = meslek_label.lower() if meslek_label else ""
    if any(x in meslek_lower for x in ["ciftci", "tarla", "coban"]):
        return "Ciftci"
    if any(x in meslek_lower for x in ["doktor", "cerrah", "hemşire", "eczaci", "patolog"]):
        return "Doktor"
    if any(x in meslek_lower for x in ["mühendis", "tamir", "cirak", "jeneratör"]):
        return "Tamirci"
    if any(x in meslek_lower for x in ["polis", "amir", "komiser", "çevik", "devriye", "trafik"]):
        return "Polis"
    if any(x in meslek_lower for x in ["vali", "tahsis", "halkla"]):
        return "Valilik"
    if any(x in meslek_lower for x in ["komutan", "yüzbaşi", "çavuş", "er", "lojistik",
                                        "paralı", "nişancı", "öncü", "bağımsız"]):
        return "Askeri"
    return "Bilinmiyor"


def _grup_isim_donustur(grup: str) -> str:
    """Config'deki grup adini MESLEK_EYLEMLERI key'ine cevir.
    Ornek: 'Hükümet Askeri' -> 'Askeri'
            'Bağımsız Askeri' -> 'Askeri'
    """
    donusum = {
        "Valilik": "Valilik",
        "Hükümet Askeri": "Askeri",
        "Bağımsız Askeri": "Askeri",
        "Polis": "Polis",
        "Çiftçi": "Ciftci",
        "Tamirci": "Tamirci",
        "Doktor": "Doktor",
    }
    return donusum.get(grup, grup)


# ==================================================================
# MESLEK VIEW (Eylem Secim Dropdown)
# ==================================================================
class MeslekEylemDropdown(discord.ui.Select):
    """Meslek eylemlerini listeler."""

    def __init__(self, eylemler: list, user_data: dict):
        self.eylemler = eylemler
        self.user_data = user_data
        options = []
        for eylem in eylemler:
            risk_yuzde = int(eylem.get('risk', 0) * 100)
            aciklama = eylem['beklenti'][:80]
            if risk_yuzde > 0:
                aciklama += f" (Risk: %{risk_yuzde})"
            options.append(discord.SelectOption(
                label=eylem['isim'],
                value=eylem['isim'],
                description=aciklama
            ))
        super().__init__(
            placeholder='Bir eylem sec...',
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        secim = self.values[0]
        eylem = next((e for e in self.eylemler if e['isim'] == secim), None)
        if not eylem:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Eylem bulunamadi."),
                ephemeral=True
            )
            return
        await interaction.response.edit_message(view=None)
        await self._eylem_uygula(interaction, eylem)

    async def _eylem_uygula(self, interaction: discord.Interaction,
                             eylem: dict):
        """Secilen eylemi uygula."""
        user_id = interaction.user.id

        # Cooldown kontrolu
        cd_kalan = await db.get_cooldown(user_id, 'meslek')
        if cd_kalan > 0:
            await interaction.followup.send(
                embed=embeds.warning_embed(
                    "Bekleme Suresi",
                    MSG_COOLDOWN_AKTIF.format(kalan_dk=cd_kalan // 60)
                ),
                ephemeral=True
            )
            return

        # Slot doluluk kontrolu
        slot_capacity = await db.get_slot_capacity(user_id)
        envanter_adet = await db.get_inventory_count(user_id)
        slot_var = (envanter_adet < slot_capacity)

        # Risk kontrolu
        risk = eylem.get('risk', 0)
        basarili = random.random() > risk

        if not basarili:
            # Basarisiz - cooldown yine de baslar
            await db.set_cooldown(user_id, 'meslek')
            await db.add_action_log('meslek', user_id, None,
                                     f"basarisiz: {eylem['isim']}", {})
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Eylem Basarisiz",
                    f"**{eylem['isim']}** eylemi basarisiz oldu. "
                    f"Kaynaklarinizi kaybettiniz."
                )
            )
            return

        # Basarili - kazanimlari uygula
        kazanim_metni = []
        kazanim = eylem.get('kazanim', eylem)
        if 'item' in kazanim:
            esya_adi = kazanim['item']
            miktar = kazanim.get('miktar', 1)
            # Slot kontrolu
            if not slot_var and esya_adi not in ['Para']:
                # Esya alinamaz - sadece para ver
                para_odul = 20
                await db.update_money(user_id, para_odul)
                kazanim_metni.append(f"Envanter dolu! Sadece {para_odul} 🪙 aldin.")
            else:
                await db.add_item(user_id, esya_adi, miktar)
                kazanim_metni.append(f"• {esya_adi} x{miktar}")

        elif 'item_rastgele' in kazanim:
            # Rastgele asi_bilesen ver
            kategori = kazanim['item_rastgele']
            bulunanlar = [isim for isim, d in ITEMS.items()
                          if d.get('kategori') == kategori]
            if bulunanlar and slot_var:
                secim = random.choice(bulunanlar)
                await db.add_item(user_id, secim, 1)
                kazanim_metni.append(f"• {secim} x1 (Rastgele)")
            elif bulunanlar and not slot_var:
                para_odul = 30
                await db.update_money(user_id, para_odul)
                kazanim_metni.append(f"Envanter dolu! {para_odul} 🪙 aldin.")
            else:
                para_odul = 25
                await db.update_money(user_id, para_odul)
                kazanim_metni.append(f"• {para_odul} 🪙")

        if 'para' in kazanim:
            para_miktar = kazanim['para']
            await db.update_money(user_id, para_miktar)
            kazanim_metni.append(f"• {format_para(para_miktar)}")

        # Cooldown baslat
        await db.set_cooldown(user_id, 'meslek')

        # Log
        await db.add_action_log('meslek', user_id, None,
                                 f"basarili: {eylem['isim']}",
                                 {'kazanimlar': kazanim_metni})

        # Mesaj
        embed = embeds.success_embed(
            f"Eylem Basarili: {eylem['isim']}",
            f"**Beklenti:** {eylem['beklenti']}\n\n"
            f"**Kazanimlar:**\n" + "\n".join(kazanim_metni)
        )
        embed.set_footer(text=f"Bekleme: 1 saat")
        await interaction.followup.send(embed=embed)


class MeslekView(discord.ui.View):
    """Meslek eylemleri dropdown view."""
    def __init__(self, eylemler: list, user_data: dict):
        super().__init__(timeout=120)
        self.add_item(MeslekEylemDropdown(eylemler, user_data))


# ==================================================================
# YANKESICILIK VIEW
# ==================================================================
class YankesicilikView(discord.ui.View):
    """Yankesicilik icin onay/red butonlari (hedefe gosterilir)."""
    def __init__(self, hedef: discord.Member, saldirgan: discord.Member):
        super().__init__(timeout=60)
        self.hedef = hedef
        self.saldirgan = saldirgan
        self.sonuc = None  # 'kabul' | 'red' | None

    @discord.ui.button(label="RP'ye Yanit Ver", emoji="✋",
                       style=discord.ButtonStyle.primary)
    async def kabul_btn(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata",
                    "Bu buton senin icin degil."),
                ephemeral=True
            )
            return
        self.sonuc = 'kabul'
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Reddet / Kac", emoji="🏃",
                       style=discord.ButtonStyle.danger)
    async def red_btn(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        if interaction.user.id != self.hedef.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata",
                    "Bu buton senin icin degil."),
                ephemeral=True
            )
            return
        self.sonuc = 'red'
        self.stop()
        await interaction.response.edit_message(view=None)


# ==================================================================
# COG SINIFI
# ==================================================================
class MeslekCog(commands.Cog):
    """Meslek eylemleri cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Aktif yankesicilik beklemede olan hedefler
        self._aktif_yankesicilik = {}  # hedef_id -> YankesicilikView

    # ==================================================================
    # /meslek
    # ==================================================================
    @commands.hybrid_command(
        name="meslek",
        description="Meslek eylemlerini gosterir"
    )
    async def meslek_slash(self, ctx: commands.Context):
        """Meslek eylemlerini listeler ve uygulatir."""
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

        meslek_label = user_data.get('meslek', '')
        grup = meslek_grubu_bul(meslek_label)

        # Eylemleri bul
        eylemler = MESLEK_EYLEMLERI.get(grup, [])
        if not eylemler:
            await self._send_error(ctx,
                f"Meslegin icin ({meslek_label}) tanimli eylem yok. "
                f"Bu meslek grupta ({grup}) eylem yok veya yakinda eklenecek."
            )
            return

        # Cooldown kontrolu
        cd_kalan = await db.get_cooldown(ctx.author.id, 'meslek')
        cd_bilgi = ""
        if cd_kalan > 0:
            cd_bilgi = f"\n\n⏳ **Bekleme:** {format_sure(cd_kalan)} kaldi."

        # Cooldown varsa dropdown yine de gosterilsin (bilgi icin)
        embed = discord.Embed(
            title=f"💼 Meslek: {meslek_label}",
            description=f"**Grup:** {grup}\n"
                        f"**Kullanici:** {ctx.author.mention}"
                        f"{cd_bilgi}",
            color=config.RENK_BILGI
        )
        embed.add_field(
            name="📋 Eylemler",
            value=f"Asagidan bir eylem sec. Her eylem 1 saat cooldown'lidir.",
            inline=False
        )

        view = MeslekView(eylemler, user_data)
        await self._send(ctx, embed=embed, view=view)

    # ==================================================================
    # /yankesicilik (cete uyesi ozel)
    # ==================================================================
    @commands.hybrid_command(
        name="yankesicilik",
        description="Bir oyuncudan gizlice esya calmaya calisir (cete uyesi)"
    )
    @app_commands.describe(
        hedef="Hedef kullanici"
    )
    async def yankesicilik_slash(self, ctx: commands.Context,
                                  hedef: discord.Member):
        """Yankesicilik eylemi."""
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

        # Cete uyesi mi?
        gang = await db.get_user_gang(ctx.author.id)
        if not gang:
            await self._send_error(ctx,
                "🚫 Yankesicilik sadece cete uyeleri icindir."
            )
            return

        # Hedef kontrolu
        if hedef.id == ctx.author.id:
            await self._send_error(ctx, "Kendinden calamazsin!")
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx, "Gozlemcilerden esya calamazsin.")
            return

        if hedef_data.get('is_dead', 0):
            await self._send_error(ctx, "Olu karakterden esya calamazsin.")
            return

        # Hedef ayni cogta mi kontrol (RP gerekcesi)
        # Bot hedefin son RP kanalini kontrol eder
        son_kanal_id = hedef_data.get('last_message_channel')
        if not son_kanal_id:
            await self._send_error(ctx,
                "Hedef kullanici son zamanlarda RP kanalinda degil. "
                "Once onun bir RP kanalinda aktif olmasi gerekir."
            )
            return

        # Ayni kanalda mi?
        if ctx.channel.id != son_kanal_id:
            kanal = self.bot.get_channel(son_kanal_id)
            kanal_ad = kanal.mention if kanal else f"<#{son_kanal_id}>"
            await self._send_error(ctx,
                f"Hedef son olarak {kanal_ad} kanalinda goruldu. "
                f"Yankesicilik icin ayni kanalda olmalisin."
            )
            return

        # Cooldown
        cd_kalan = await db.get_cooldown(ctx.author.id, 'yankesicilik')
        if cd_kalan > 0:
            await self._send_error(ctx,
                MSG_COOLDOWN_AKTIF.format(kalan_dk=cd_kalan // 60)
            )
            return

        # Hedef envanteri kontrol
        hedef_envanter = await db.get_inventory(hedef.id)
        if not hedef_envanter:
            await self._send_error(ctx,
                f"{hedef.mention} adli kisinin envanteri bos. Calinacak esya yok."
            )
            return

        # Yankesicilik baslat - hedefe bildir
        view = YankesicilikView(hedef, ctx.author)
        embed = discord.Embed(
            title="🦹 Yankesicilik Tespit Edildi!",
            description=(
                f"{hedef.mention}, {ctx.author.mention} tarafindan "
                f"yankesicilige maruz kaldin!\n\n"
                f"**Ne yapmak istersin?**\n"
                f"✋ **RP'ye yanit ver** - Kavgaya/kacisa hazirla\n"
                f"🏃 **Reddet / Kac** - Sadece kacmaya calis"
            ),
            color=config.RENK_UYARI
        )
        embed.set_footer(text="60 saniye icinde yanit vermezsen otomatik red olur.")
        await self._send(ctx, content=hedef.mention, embed=embed, view=view)

        # Bekleme (60 sn timeout)
        await view.wait()

        if view.sonuc is None or view.sonuc == 'red':
            # Red / timeout - saldirgan basarisiz, hedef haberdar
            await db.set_cooldown(ctx.author.id, 'yankesicilik')
            await db.add_action_log('yankesicilik', ctx.author.id, hedef.id,
                                     'kacirildi', {'sonuc': view.sonuc})
            await self._send(ctx, 
                embed=embeds.error_embed(
                    "Yankesicilik Basarisiz",
                    f"{hedef.mention} kacmayi basardi veya yanit vermedi. "
                    f"2 saat cooldown basladi."
                )
            )
            return

        # Kabul - zar atma mekanigi
        saldirgan_zar = random.randint(1, 20)
        hedef_zar = random.randint(1, 20)

        embed = discord.Embed(
            title="🎲 Zar Atisi",
            color=config.RENK_CETE,
            description=(
                f"**Saldirgan ({ctx.author.mention}):** {saldirgan_zar}\n"
                f"**Hedef ({hedef.mention}):** {hedef_zar}\n\n"
            )
        )

        if saldirgan_zar > hedef_zar:
            # Basarili calma - rastgele 1 kucuk esya
            # Kucuk esya = yiyecek/icecek/malzeme (silah degil)
            kucuk_esyalar = [
                i for i in hedef_envanter
                if ITEMS.get(i['item'], {}).get('kategori', 'diger')
                in ['yiyecek', 'icecek', 'malzeme', 'medikal']
            ]
            if not kucuk_esyalar:
                # Sadece buyuk esya varsa, bir tane al
                kucuk_esyalar = hedef_envanter

            calinan = random.choice(kucuk_esyalar)
            await db.remove_item(hedef.id, calinan['item'], 1)
            await db.add_item(ctx.author.id, calinan['item'], 1)

            embed.add_field(
                name="✅ Basarili",
                value=f"**Calinan esya:** {calinan['item']} x1\n"
                      f"Esya envantere eklendi.",
                inline=False
            )
            await db.add_action_log('yankesicilik', ctx.author.id, hedef.id,
                                     'basarili',
                                     {'esya': calinan['item'],
                                      'saldirgan_zar': saldirgan_zar,
                                      'hedef_zar': hedef_zar})
        else:
            # Basarisiz
            embed.add_field(
                name="❌ Basarisiz",
                value=f"Yankesicilik basarisiz oldu. Hedef seni fark etti!\n"
                      f"RP kavgasi/kacisi baslayabilir.",
                inline=False
            )
            await db.add_action_log('yankesicilik', ctx.author.id, hedef.id,
                                     'basarisiz',
                                     {'saldirgan_zar': saldirgan_zar,
                                      'hedef_zar': hedef_zar})

        await db.set_cooldown(ctx.author.id, 'yankesicilik')
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
    await bot.add_cog(MeslekCog(bot))
    logger.info("MeslekCog yuklendi")
