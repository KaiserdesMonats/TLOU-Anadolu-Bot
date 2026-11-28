"""
cogs/envanter.py - Envanter Sistemi
Hybrid komutlar: /envanter, /slot-gelistir
Kullanici esyalarini goruntuler ve slot kapasitesini gelistirir.
"""
import logging
import random
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.checks import is_kayitli
from utils.constants import (
    ITEMS, esya_bul, esya_onerileri, esya_isim_normalize,
)
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
        esya="Bilgi alinacak esya adi (yazmaya baslayinca oneriler cikar)"
    )
    async def esya_bilgi_slash(self, ctx: commands.Context, esya: str):
        """Bir esyanin detaylarini gosterir.

        FIX (v0.2.0): Eski kod isimleri birebir karsilastiriyordu; oyuncular
        'Kirli Sargı' yazdiginda ITEMS'teki 'Kirli Sargi' ile eslesmiyor ve
        esya 'bulunamadi' hatasi veriyordu. Artik Turkce toleransli arama
        (esya_bul) kullaniliyor + slash'da autocomplete var.
        """
        user_data = await db.get_user(ctx.author.id)
        if not user_data or user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        # Esya listede var mi? (Turkce/ASCII farki tolere edilir)
        esya_bulundu = esya_bul(esya)

        if not esya_bulundu:
            await self._send_error(ctx,
                f"'{esya}' adli esya bulunamadi. "
                f"Toplam {len(ITEMS)} esya var. "
                f"Ipucu: `/esya-bilgi` yazinca esya onerileri listelenir "
                f"(orn: 'Kirli Sargi', 'Su Sisesi')."
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
        if 'tokluk' in detay:
            etkiler.append(f"🍖 Tokluk +{detay['tokluk']}")
        if 'susuzluk' in detay:
            etkiler.append(f"💧 Susuzluk +{detay['susuzluk']}")
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

        # /kullan ile kullanilabilir mi?
        kullanilabilir = any(k in detay for k in
                             ('can', 'susuzluk', 'tokluk', 'acluk'))
        if kullanilabilir:
            embed.add_field(name="🖐️ Kullanim",
                            value="`/kullan esya:" + isim + "` ile "
                                  "kullanabilirsin.",
                            inline=True)
        elif 'hasar' in detay:
            embed.add_field(name="🖐️ Kullanim",
                            value="Silah - RP icinde kullanilir.", inline=True)
        elif kategori == 'asi_bilesen' or isim == 'Asi':
            embed.add_field(name="🖐️ Kullanim",
                            value="Aşı üretiminde malzeme olarak kullanılır.",
                            inline=True)
        else:
            embed.add_field(name="🖐️ Kullanim",
                            value="Tuketilebilir degil.", inline=True)

        # Kullanicinin bu esyadan kac tane var? (normalize eslesme)
        envanter = await db.get_inventory(ctx.author.id)
        sahip_oldugu = sum(
            i['amount'] for i in envanter
            if esya_isim_normalize(i['item']) == esya_isim_normalize(isim)
        )
        embed.add_field(name="📊 Senin Envanterinde",
                        value=f"**{sahip_oldugu}** adet", inline=True)

        embed.set_footer(text=f"User ID: {ctx.author.id}")
        await self._send(ctx, embed=embed)

    @esya_bilgi_slash.autocomplete("esya")
    async def esya_bilgi_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """FIX (v0.2.0): /esya-bilgi'de 'esyalar gozukmuyor' sikayeti icin
        esya adina autocomplete eklendi. ITEMS listesinden oneriler.
        """
        return [
            app_commands.Choice(name=name, value=name)
            for name in esya_onerileri(current)
        ]

    # ==================================================================
    # /kullan (v0.2.0 - YENI)
    # ==================================================================
    @commands.hybrid_command(
        name="kullan",
        description="Envanterindeki tuketilebilir esyayi kullan (yemek, icecek, sargi vb.)"
    )
    @app_commands.describe(
        esya="Kullanilacak esya (oneriler icin yazmaya basla)",
        miktar="Kac adet kullanilsin (varsayilan: 1)"
    )
    async def kullan_slash(self, ctx: commands.Context, esya: str,
                           miktar: int = 1):
        """Tuketilebilir esya kullanir.

        Yiyecek acluk +, icecek susuzluk +, sargi/ilac can + verir.
        Kirli Su icindigi zaman enfeksiyon riski vardir.
        """
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

        if miktar <= 0:
            await self._send_error(ctx, "Miktar 1'den kucuk olamaz.")
            return

        # Esyayi bul (Turkce toleransli)
        bulundu = esya_bul(esya)
        if not bulundu:
            await self._send_error(ctx,
                f"'{esya}' adli esya bulunamadi. "
                f"`/esya-bilgi` ile esya isimlerine bakabilirsin."
            )
            return
        isim, detay = bulundu

        # Tuketilebilir mi?
        etkiler_anahtar = [k for k in ('can', 'susuzluk', 'tokluk', 'acluk')
                            if k in detay]
        if not etkiler_anahtar:
            await self._send_error(ctx,
                f"**{isim}** tuketilebilir bir esya degil "
                f"(silah/malzeme esyalari bu komutla kullanilamaz)."
            )
            return

        # Envanterde yeterli var mi?
        envanter = await db.get_inventory(ctx.author.id)
        sahip = next(
            (i['amount'] for i in envanter
             if esya_isim_normalize(i['item']) == esya_isim_normalize(isim)),
            0
        )
        if sahip <= 0:
            await self._send_error(ctx,
                f"Envanterinde **{isim}** yok. `/envanter` ile bakabilirsin."
            )
            return
        kullanilan = min(miktar, sahip)

        # Etkileri hesapla (statlar 100'u asamaz)
        can_artis = int(detay.get('can', 0)) * kullanilan
        susuzluk_artis = int(detay.get('susuzluk', 0)) * kullanilan
        # 'tokluk' ve 'acluk' ayni stat (acluk 100 = tok)
        acluk_artis = (int(detay.get('acluk', 0))
                        + int(detay.get('tokluk', 0))) * kullanilan

        mevcut_can = user_data.get('can', 100) or 0
        mevcut_acluk = user_data.get('acluk', 100) or 0
        mevcut_susuzluk = user_data.get('susuzluk', 100) or 0

        can_artis = min(can_artis, max(0, 100 - mevcut_can))
        acluk_artis = min(acluk_artis, max(0, 100 - mevcut_acluk))
        susuzluk_artis = min(susuzluk_artis, max(0, 100 - mevcut_susuzluk))

        # Kirli Su enfeksiyon riski (adet basina zar; en az biri bulastralir)
        enfeksiyon_risk = detay.get('risk', 0)
        enfeksiyon_sonucu = None
        if enfeksiyon_risk:
            olasilik = 1 - ((1 - enfeksiyon_risk) ** kullanilan)
            if random.random() < olasilik:
                durum = await db.get_enfeksiyon_durumu(ctx.author.id)
                if not durum['var']:
                    await db.set_enfeksiyon(
                        ctx.author.id, config.ENFEKSIYON_TOPLAM_SURE, 1
                    )
                    enfeksiyon_sonucu = (
                        "🦠 **Kirli su basina bulasti!** Enfeksiyon basladi. "
                        "Bir doktora gitmelisin!"
                    )
                else:
                    enfeksiyon_sonucu = (
                        "🦠 Zaten enfekte oldugun icin yeni bir sey degismedi."
                    )

        # Esyayi envanterden dus
        await db.remove_item(ctx.author.id, isim, kullanilan)

        # Statlari guncelle
        # DIKKAT: update_stats icin goreceli artis '+X' string olmalidir,
        # aksi halde stat o degerle EZILIR (can=10 gibi).
        stat_guncellemeleri = {}
        if can_artis > 0:
            stat_guncellemeleri['can'] = f"+{can_artis}"
        if acluk_artis > 0:
            stat_guncellemeleri['acluk'] = f"+{acluk_artis}"
        if susuzluk_artis > 0:
            stat_guncellemeleri['susuzluk'] = f"+{susuzluk_artis}"
        if stat_guncellemeleri:
            await db.update_stats(ctx.author.id, **stat_guncellemeleri)

        # Log
        await db.add_action_log(
            'envanter', ctx.author.id, None, 'kullan',
            {'esya': isim, 'miktar': kullanilan,
             'can': can_artis, 'acluk': acluk_artis,
             'susuzluk': susuzluk_artis}
        )

        # Embed
        etkiler_metni = []
        if can_artis > 0:
            etkiler_metni.append(f"❤️ Can +{can_artis} "
                                 f"({mevcut_can + can_artis}/100)")
        if acluk_artis > 0:
            etkiler_metni.append(f"🍖 Aclik +{acluk_artis} "
                                 f"({mevcut_acluk + acluk_artis}/100)")
        if susuzluk_artis > 0:
            etkiler_metni.append(f"💧 Susuzluk +{susuzluk_artis} "
                                 f"({mevcut_susuzluk + susuzluk_artis}/100)")

        if etkiler_metni:
            embed = embeds.success_embed(
                f"{isim} Kullanildi (x{kullanilan})",
                "\n".join(etkiler_metni)
            )
        else:
            # Statlar zaten dolu - esya harcandi
            embed = embeds.warning_embed(
                f"{isim} Kullanildi (x{kullanilan})",
                "Ilgili statlarin zaten doluydu, esya harcandi."
            )

        if enfeksiyon_sonucu:
            embed.add_field(name="🦠 Enfeksiyon",
                            value=enfeksiyon_sonucu, inline=False)

        embed.set_footer(text=f"Envanterinde kalan: {sahip - kullanilan} adet")
        await self._send(ctx, embed=embed)

    @kullan_slash.autocomplete("esya")
    async def kullan_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """Sadece tuketilebilir esyalari one cikar (can/susuzluk/tokluk etkisi olanlar)."""
        current_norm = esya_isim_normalize(current)
        choices = []
        for name, detay in ITEMS.items():
            if not any(k in detay for k in ('can', 'susuzluk', 'tokluk', 'acluk')):
                continue
            name_norm = esya_isim_normalize(name)
            if not current_norm or current_norm in name_norm:
                choices.append(app_commands.Choice(name=name, value=name))
            if len(choices) >= 25:
                break
        return choices

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
