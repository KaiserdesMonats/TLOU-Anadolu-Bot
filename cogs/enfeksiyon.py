"""
cogs/enfeksiyon.py - Enfeksiyon Sistemi
Hybrid komutlar: /enfeksiyon, /doktor-mudahale, /asi-uret, /asi-uygula, /rituel
4 asamali zombilesme suresi (toplam 72 saat = 3 gun).
"""
import logging
import time
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import ASI_BILESENLERI, ITEMS
from utils.formatting import format_sure, format_tarih
from utils.localization import (
    MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
    MSG_ENFEKSIYON_TEMIZ, MSG_DOKTOR_MUDAHALE,
    MSG_ASİ_URETILDI,
)


logger = logging.getLogger("tlo.cogs.enfeksiyon")


# ==================================================================
# MESLEK KONTROL YARDIMCILARI
# ==================================================================
# Bashekim/Cerrah rol ID'si
ROL_BASHEKIM_ID = 1569762333914439781  # ⚕️ • Başhekim / Cerrah


def _kullanici_meslek_idleri(member) -> set:
    """Kullanicinin sahip oldugu meslek rol ID'lerini dondur."""
    if not member:
        return set()
    return {r.id for r in member.roles}


def is_doktor(user_data: dict, member=None) -> bool:
    """Kullanici doktor meslek grubundan mi?
    Once rol ID'sine bakar, sonra meslek adina.
    """
    # Rol ID kontrolu (daha guvenilir)
    if member:
        doktor_rol_idleri = {
            1569762333914439781,  # Başhekim / Cerrah
            1569765127316840520,  # Eczacı
            1569765212372861058,  # Hemşire / İlk Yardımcı
            1569765270858367136,  # Araştırmacı / Patolog
        }
        if doktor_rol_idleri & _kullanici_meslek_idleri(member):
            return True
    # Meslek adina gore fallback
    meslek = (user_data.get('meslek') or '').lower()
    doktor_anahtarlar = [
        'doktor', 'cerrah', 'hemşire', 'hemsire', 'eczacı', 'eczaci',
        'patolog', 'başhekim', 'bashekim', 'ilk yardımcı', 'ilk yardimci',
        'araştırmacı', 'arastirmaci'
    ]
    return any(x in meslek for x in doktor_anahtarlar)


def is_tarikat(user_data: dict, member=None) -> bool:
    """Kullanici tarikat cesinden mi?"""
    # Rol ID kontrolu
    if member:
        tarikat_rol_idleri = {
            1569767025985851446,  # Mürşit
            1569767100921282671,  # Vaiz
            1569767165685538886,  # Fedai
            1569767215383842938,  # İnisiye
            1573676565429092482,  # Tarikat Çete Üyesi
        }
        if tarikat_rol_idleri & _kullanici_meslek_idleri(member):
            return True
    # Fallback
    meslek = (user_data.get('meslek') or '').lower()
    tarikat_anahtarlar = ['mürşit', 'murşit', 'mursit', 'vaiz', 'fedai',
                          'inisiye', 'tarikat']
    return any(x in meslek for x in tarikat_anahtarlar)


def is_bashekim(user_data: dict, member=None) -> bool:
    """Sadece Bashekim/Cerrah asi uretebilir.
    Once rol ID'sine bakar (daha guvenilir), sonra meslek adina.
    """
    # Rol ID kontrolu - EN GUVENILIR
    if member:
        if ROL_BASHEKIM_ID in _kullanici_meslek_idleri(member):
            return True
    # Meslek adina gore fallback
    meslek = (user_data.get('meslek') or '').lower()
    return any(anahtar in meslek for anahtar in
               ('başhekim', 'bashekim', 'cerrah', '⁣bashekim / cerrah'))


# ==================================================================
# COG SINIFI
# ==================================================================
class EnfeksiyonCog(commands.Cog):
    """Enfeksiyon ve asi sistemi cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /enfeksiyon (durum sorgulama)
    # ==================================================================
    @commands.hybrid_command(
        name="enfeksiyon",
        description="Enfeksiyon durumunu gosterir"
    )
    async def enfeksiyon_slash(self, ctx: commands.Context):
        """Kullanici enfeksiyon durumunu gosterir."""
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

        durum = await db.get_enfeksiyon_durumu(ctx.author.id)

        if not durum['var']:
            await self._send(ctx, embed=embeds.success_embed(
                "Enfeksiyon Durumu",
                MSG_ENFEKSIYON_TEMIZ
            ))
            return

        # Asama bilgisi
        sev = durum['seviye']
        asama_ad = config.ENFEKSIYON_ASAMA_ISIMLERI.get(sev, "Bilinmeyen")
        kalan_saat = durum['kalan_sure'] // 3600
        kalan_dakika = (durum['kalan_sure'] % 3600) // 60

        # Asama ilerlemesi (0-100%)
        asama_baslangic = (sev - 1) * (config.ENFEKSIYON_TOPLAM_SURE //
                                        config.ENFEKSIYON_ASAMA_SAYISI)
        asama_bitis = sev * (config.ENFEKSIYON_TOPLAM_SURE //
                              config.ENFEKSIYON_ASAMA_SAYISI)
        gecen_asama = max(0, durum['gecen_sure'] - asama_baslangic)
        asama_suresi = asama_bitis - asama_baslangic
        asama_yuzde = int((gecen_asama / asama_suresi) * 100) if asama_suresi > 0 else 0

        embed = discord.Embed(
            title="🦠 Enfeksiyon Durumu",
            description=(
                f"**Asama:** {sev}/4 - {asama_ad}\n"
                f"**Kalan Sure:** {kalan_saat} saat {kalan_dakika} dakika\n"
                f"**Toplam Sure:** {format_sure(durum['toplam_sure'])}\n"
                f"**Gecen Sure:** {format_sure(durum['gecen_sure'])}"
            ),
            color=config.RENK_ENFEKSIYON
        )

        # Asama ilerleme cubugu
        bar_dolu = "█" * (asama_yuzde // 10)
        bar_bos = "░" * (10 - len(bar_dolu))
        embed.add_field(
            name=f"Asama {sev} Ilerlemesi ({asama_yuzde}%)",
            value=f"`{bar_dolu}{bar_bos}`",
            inline=False
        )

        # Asama aciklamalari
        asama_aciklamalar = {
            1: "Hafif yorgunluk, arada bas agrisi. Hasta enfeksiyonun farkinda olmayabilir.",
            2: "Ateş, titreme, kas agrilari. Mantar sporlari kan dolasimina yayiliyor.",
            3: "Siddetli hassasiyet, bilinc bulanikligi. Vucut donusum surecinde.",
            4: "Kritik donem. Karakterin bilinci kaybolmak uzere. Yakinda donecek."
        }
        embed.add_field(
            name="📋 Semptomlar",
            value=asama_aciklamalar.get(sev, "Bilinmeyen asama."),
            inline=False
        )

        # Cozum yollari
        embed.add_field(
            name="⚕️ Cozum",
            value=(
                "• **Doktor mudahalesi** sureyi uzatabilir (geciktirme)\n"
                "• **Asi** tamamen iyilestirir (cok nadir)\n"
                "• **Tarikat ritueli** (varsa) ilerlemeyi %10 yavaslatabilir"
            ),
            inline=False
        )

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /doktor-mudahale
    # ==================================================================
    @commands.hybrid_command(
        name="doktor-mudahale",
        description="Bir hastanin enfeksiyon suresini uzatir (sadece doktor)"
    )
    @app_commands.describe(
        hedef="Mudahale edilecek hasta kullanici"
    )
    async def doktor_mudahale_slash(self, ctx: commands.Context,
                                     hedef: discord.Member):
        """Doktor, bir hastanin enfeksiyon suresini uzatir."""
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

        if not is_doktor(user_data, ctx.author):
            await self._send_error(ctx,
                "🚫 Bu komutu sadece doktor meslek grubu kullanicilari kullanabilir."
            )
            return

        # Hedef kontrol
        if hedef.id == ctx.author.id:
            await self._send_error(ctx, "Kendine mudahale edemezsin.")
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if hedef_data.get('is_dead', 0):
            await self._send_error(ctx, "Olu karaktere mudahale edilemez.")
            return
        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx, "Gozlemcilere mudahale edilemez.")
            return

        # Hedef enfekte mi?
        durum = await db.get_enfeksiyon_durumu(hedef.id)
        if not durum['var']:
            await self._send_error(ctx,
                f"{hedef.mention} enfekte degil. Mudahale gerekmez."
            )
            return

        # Ayni kanalda mi kontrol (RP gerekcesi)
        if ctx.channel.id != hedef_data.get('last_message_channel'):
            await self._send_error(ctx,
                f"{hedef.mention} son olarak baska bir kanalda goruldu. "
                f"Mudahale icin ayni kanalda olmalisin."
            )
            return

        # Mudahale ucreti (RP gerekcesi)
        # Bashekim daha pahali ama daha uzun uzatma
        is_bashekim_rolu = is_bashekim(user_data, ctx.author)
        if is_bashekim_rolu:
            ek_sure = 8 * 3600   # 8 saat
            ucret = 100
            mudahale_turu = "Cerrahi mudahale"
        else:
            ek_sure = 4 * 3600   # 4 saat
            ucret = 50
            mudahale_turu = "Ilk yardim mudahalesi"

        # Para kontrol
        if user_data['para'] < ucret:
            await self._send_error(ctx,
                f"Mudahale icin {ucret} 🪙 gerekir."
            )
            return

        # Mudahale uygula
        await db.update_money(ctx.author.id, -ucret)
        await db.extend_enfeksiyon(hedef.id, ek_sure)

        # Log
        await db.add_action_log('enfeksiyon', ctx.author.id, hedef.id,
                                 'doktor_mudahale',
                                 {'sure': ek_sure, 'ucret': ucret,
                                  'tur': mudahale_turu})

        # Enfeksiyon log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="⚕️ Doktor Mudahalesi",
                description=(
                    f"**Doktor:** {ctx.author.mention}\n"
                    f"**Hasta:** {hedef.mention}\n"
                    f"**Mudahale:** {mudahale_turu}\n"
                    f"**Ek Sure:** +{format_sure(ek_sure)}\n"
                    f"**Ucret:** {ucret} 🪙"
                ),
                color=config.RENK_BILGI,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"enfeksiyon-log gonderilemedi: {e}")

        # Basari mesaji
        embed = embeds.success_embed(
            f"{mudahale_turu} Basarili",
            f"{hedef.mention} enfeksiyon suresi **+{format_sure(ek_sure)}** uzatildi.\n"
            f"Ucret: {ucret} 🪙"
        )

        # Hedefe bildirim
        await self._send(ctx, content=hedef.mention, embed=embed)

    # ==================================================================
    # /asi-uret (sadece Bashekim/Cerrah)
    # ==================================================================
    @commands.hybrid_command(
        name="asi-uret",
        description="Asi uretir (sadece Bashekim/Cerrah)"
    )
    async def asi_uret_slash(self, ctx: commands.Context):
        """Asi uretir. Cok zor ve pahali bir surectir."""
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

        if not is_bashekim(user_data, ctx.author):
            await self._send_error(ctx,
                "🚫 Asi uretmek icin **Bashekim** veya **Cerrah** olmaniz gerekir."
            )
            return

        # 5 asi bileseni gerekli
        envanter = await db.get_inventory(ctx.author.id)
        envanter_dict = {i['item']: i['amount'] for i in envanter}

        eksikler = []
        for bilesen in ASI_BILESENLERI:
            if envanter_dict.get(bilesen, 0) < 1:
                eksikler.append(bilesen)

        if eksikler:
            await self._send_error(ctx,
                f"Asi uretmek icin **5 farkli bilesen** gerekir:\n"
                + "\n".join(f"• {b}" for b in ASI_BILESENLERI) +
                f"\n\n**Eksik bilesenler:**\n"
                + "\n".join(f"❌ {b}" for b in eksikler)
            )
            return

        # Tum bilesenler var, uret
        for bilesen in ASI_BILESENLERI:
            await db.remove_item(ctx.author.id, bilesen, 1)

        # Asi ekle
        await db.add_item(ctx.author.id, "Asi", 1)

        # Log
        await db.add_action_log('enfeksiyon', ctx.author.id, None,
                                 'asi_uret',
                                 {'bilesenler': ASI_BILESENLERI})

        # Enfeksiyon log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="💉 Asi Uretildi!",
                description=(
                    f"**Uretici:** {ctx.author.mention} (Bashekim/Cerrah)\n"
                    f"**Miktar:** 1 adet\n"
                    f"**Kullanilan bilesenler:**\n"
                    + "\n".join(f"• {b}" for b in ASI_BILESENLERI)
                ),
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"enfeksiyon-log gonderilemedi: {e}")

        # Basari mesaji
        embed = embeds.success_embed(
            "💉 Asi Uretildi!",
            "Tebrikler! 1 adet **Asi** uretildi.\n"
            "Bu asi, bir hastayi enfeksiyondan tamamen iyilestirebilir.\n\n"
            "Kullanmak icin: `/asi-uygula @hasta`"
        )

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /asi-uygula (sadece Bashekim/Cerrah)
    # ==================================================================
    @commands.hybrid_command(
        name="asi-uygula",
        description="Hastaya asi uygular ve enfeksiyonu tamamen temizler"
    )
    @app_commands.describe(
        hedef="Asi uygulanacak kullanici"
    )
    async def asi_uygula_slash(self, ctx: commands.Context,
                                hedef: discord.Member):
        """Hastaya asi uygular."""
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

        if not is_bashekim(user_data, ctx.author):
            await self._send_error(ctx,
                "🚫 Asi uygulamak icin **Bashekim** veya **Cerrah** olmaniz gerekir."
            )
            return

        if hedef.id == ctx.author.id:
            await self._send_error(ctx, "Kendine asi uygulayamazsin.")
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if hedef_data.get('is_dead', 0):
            await self._send_error(ctx, "Olu karaktere asi uygulanamaz.")
            return
        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx, "Gozlemcilere asi uygulanamaz.")
            return

        # Asiyi envanterden kontrol et
        asi_var = await db.has_item(ctx.author.id, "Asi", 1)
        if not asi_var:
            await self._send_error(ctx,
                "Envanterinde Asi yok. Once `/asi-uret` ile uret."
            )
            return

        # Hedef enfekte mi?
        durum = await db.get_enfeksiyon_durumu(hedef.id)
        if not durum['var']:
            await self._send_error(ctx,
                f"{hedef.mention} enfekte degil. Asi gerekmez."
            )
            return

        # Ayni kanalda mi kontrol
        if ctx.channel.id != hedef_data.get('last_message_channel'):
            await self._send_error(ctx,
                f"{hedef.mention} baska kanalda. Ayni kanalda olmalisin."
            )
            return

        # Asiyi sil ve enfeksiyonu temizle
        await db.remove_item(ctx.author.id, "Asi", 1)
        await db.clear_enfeksiyon(hedef.id)

        # Log
        await db.add_action_log('enfeksiyon', ctx.author.id, hedef.id,
                                 'asi_uygula',
                                 {'onceki_seviye': durum['seviye']})

        # Enfeksiyon log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="💉 Asi Uygulandi",
                description=(
                    f"**Doktor:** {ctx.author.mention}\n"
                    f"**Hasta:** {hedef.mention}\n"
                    f"**Onceki Asama:** {durum['seviye']}/4\n"
                    f"**Sonuc:** Enfeksiyon tamamen temizlendi"
                ),
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"enfeksiyon-log gonderilemedi: {e}")

        # Basari mesaji
        embed = embeds.success_embed(
            "💉 Asi Basariyla Uygulandi",
            f"{hedef.mention} enfeksiyonu tamamen temizlendi!\n"
            f"Onceki asama: **{durum['seviye']}/4**\n"
            f"Kullanilan asi: 1 adet"
        )
        await self._send(ctx, content=hedef.mention, embed=embed)

    # ==================================================================
    # /rituel (tarikat cete ozel)
    # ==================================================================
    @commands.hybrid_command(
        name="rituel",
        description="Tarikat ritueli: enfeksiyon ilerlemesini %10 yavaslatabilir"
    )
    async def rituel_slash(self, ctx: commands.Context):
        """Tarikat ritueli ile enfeksiyonu yavaslatabilir (iyilestirmez)."""
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

        # Tarikat cesinden mi kontrol (cete tipi)
        cete = await db.get_user_gang(ctx.author.id)
        if not cete or cete.get('type') != 'Tarikat Çetesi':
            await self._send_error(ctx,
                "🚫 Bu komut sadece **Tarikat Çetesi** uyeleri icindir."
            )
            return

        # Kullanici enfekte mi?
        durum = await db.get_enfeksiyon_durumu(ctx.author.id)
        if not durum['var']:
            await self._send_error(ctx,
                "Enfekte degilsin. Rituele gerek yok."
            )
            return

        # Kör Inanc perki var mi?
        cete_data = await db.get_gang_by_id(cete['gang_id'])
        perkler = cete_data.get('perks', []) if cete_data else []
        if isinstance(perkler, str):
            import json
            try:
                perkler = json.loads(perkler)
            except Exception:
                perkler = []

        if 'kor_inanc' not in perkler:
            await self._send_error(ctx,
                "🚫 Cetenizde **Kör Inanc** perki yok. "
                "Bu komutu kullanamazsiniz."
            )
            return

        # Cooldown kontrol (6 saat - rituel cok yorucu)
        cd_kalan = await db.get_cooldown(ctx.author.id, 'rituel')
        if cd_kalan > 0:
            await self._send_error(ctx,
                f"Rituel icin {format_sure(cd_kalan)} beklemelisin."
            )
            return

        # Rituel etkisi: mevcut kalan sureyi %10 artir
        # Yani ilerlemeyi yavaslatabilir (geciktirme)
        ek_sure = int(durum['kalan_sure'] * 0.10)
        if ek_sure < 3600:  # en az 1 saat
            ek_sure = 3600

        await db.extend_enfeksiyon(ctx.author.id, ek_sure)
        await db.set_cooldown(ctx.author.id, 'rituel')

        # Log
        await db.add_action_log('enfeksiyon', ctx.author.id, None,
                                 'rituel',
                                 {'ek_sure': ek_sure})

        # Enfeksiyon log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="📿 Tarikat Ritueli",
                description=(
                    f"**Uye:** {ctx.author.mention}\n"
                    f"**Cete:** {cete.get('name', '?')}\n"
                    f"**Etki:** +{format_sure(ek_sure)} (ilerleme yavasti)\n"
                    f"**Not:** Bu rituel enfeksiyonu iyilestirmez, sadece oyalamadir."
                ),
                color=config.RENK_CETE,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"enfeksiyon-log gonderilemedi: {e}")

        # Basari mesaji
        embed = discord.Embed(
            title="📿 Rituel Tamamlandi",
            description=(
                f"Inanclarinizin gucuyle enfeksiyon ilerlemesini yavaslattiniz!\n"
                f"**Ek Sure:** +{format_sure(ek_sure)}\n"
                f"**Yeni Kalan:** {format_sure(durum['kalan_sure'] + ek_sure)}\n\n"
                f"⚠️ **Uyari:** Bu rituel enfeksiyonu iyilestirmez. "
                f"Sadece oyalamaktir. Gercek tedavi icin doktora basvurun."
            ),
            color=config.RENK_CETE
        )
        embed.set_footer(text="Rituel cooldown: 6 saat")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /isir (admin yetkili - bir kisiyi isirir)
    # ==================================================================
    @commands.hybrid_command(
        name="isirit",
        description="[RP Yetkilisi] Bir kisiyi enfekte eder (isirma)"
    )
    @app_commands.describe(
        hedef="Isirilacak kullanici",
        siddet="Isirma siddeti (1=hafif, 4=cok siddetli)"
    )
    @app_commands.choices(siddet=[
        app_commands.Choice(name="Hafif Isik (1. asama, 72 saat)", value=1),
        app_commands.Choice(name="Orta Isik (2. asama, 54 saat)", value=2),
        app_commands.Choice(name="Agir Isik (3. asama, 36 saat)", value=3),
        app_commands.Choice(name="Kritik Isik (4. asama, 18 saat)", value=4),
    ])
    async def isirit_slash(self, ctx: commands.Context, hedef: discord.Member,
                          siddet: app_commands.Choice[int]):
        """RP yetkilisi bir kisiyi isirir."""
        from utils.checks import is_rp_yetkili
        if not is_rp_yetkili(ctx.author):
            await self._send_error(ctx,
                "🚫 Bu komutu sadece **RP Yetkilisi** ve **Admin** kullanabilir."
            )
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx, "Gozlemciler isiramaz.")
            return

        if hedef_data.get('is_dead', 0):
            await self._send_error(ctx, "Olu karakter isiramaz.")
            return

        # Zaten enfekte mi?
        durum = await db.get_enfeksiyon_durumu(hedef.id)
        if durum['var']:
            await self._send_error(ctx,
                f"{hedef.mention} zaten enfekte (asama {durum['seviye']})."
            )
            return

        # Siddete gore sure belirle
        siddet_degeri = siddet.value
        if siddet_degeri == 1:
            sure = 72 * 3600
            baslangic_seviye = 1
            siddet_ad = "Hafif"
        elif siddet_degeri == 2:
            sure = 54 * 3600
            baslangic_seviye = 2
            siddet_ad = "Orta"
        elif siddet_degeri == 3:
            sure = 36 * 3600
            baslangic_seviye = 3
            siddet_ad = "Agir"
        else:  # 4
            sure = 18 * 3600
            baslangic_seviye = 4
            siddet_ad = "Kritik"

        # Enfeksiyon baslat
        await db.set_enfeksiyon(hedef.id, sure, baslangic_seviye)

        # Log
        await db.add_action_log('enfeksiyon', ctx.author.id, hedef.id,
                                 'isirit',
                                 {'siddet': siddet_ad, 'sure': sure,
                                  'baslangic_seviye': baslangic_seviye})

        # Enfeksiyon log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="🦷 Isirma Olayi",
                description=(
                    f"**Yetkili:** {ctx.author.mention}\n"
                    f"**Hedef:** {hedef.mention}\n"
                    f"**Siddet:** {siddet_ad}\n"
                    f"**Baslangic Asama:** {baslangic_seviye}/4\n"
                    f"**Toplam Sure:** {format_sure(sure)}"
                ),
                color=config.RENK_ENFEKSIYON,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"enfeksiyon-log gonderilemedi: {e}")

        # Basari mesaji (hedefe bildirim)
        embed = embeds.warning_embed(
            "🦷 Isirildin!",
            f"Tarafindan isirildin! **{siddet_ad}** siddetli bir isirma.\n"
            f"Enfeksiyon basladi. Asama: **{baslangic_seviye}/4**\n"
            f"Kalan sure: {format_sure(sure)}\n\n"
            f"⚙️ `/enfeksiyon` ile durumunu kontrol edebilirsin."
        )
        await self._send(ctx, content=hedef.mention, embed=embed)

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
                    await self._send(ctx, content, embed=embed, view=view)
                else:
                    await self._send(ctx, embed=embed, view=view)
        except Exception as e:
            logger.error(f"Mesaj gönderme hatası: {e}")
            try:
                if content:
                    await self._send(ctx, content, embed=embed, view=view)
                else:
                    await self._send(ctx, embed=embed, view=view)
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
    await bot.add_cog(EnfeksiyonCog(bot))
    logger.info("EnfeksiyonCog yuklendi")
