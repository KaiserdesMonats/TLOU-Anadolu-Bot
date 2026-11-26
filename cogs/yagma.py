"""
cogs/yagma.py - Yagma, Arastirma, Enfekte Temizleme
Hybrid komutlar: /yagma, /arastir, /enfekte-temizle
Global 3 saatlik cooldown (tum 3 komut paylasir).
Bolge kontrolu: cete bolgesinde harac kesilir.
"""
import logging
import random
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import YAGMA_KAZANIMLAR, YAGMA_PARA_SANSI
from utils.formatting import format_sure, format_para
from utils.localization import (
    MSG_COOLDOWN_AKTIF, MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
    MSG_BOLGE_KILITLI, MSG_YAGMA_BASARILI, MSG_YAGMA_BASARISIZ,
    MSG_ARASTIR_BASARILI, MSG_ENFEKTE_TEMIZLENDI,
)


logger = logging.getLogger("tlo.cogs.yagma")


# ==================================================================
# KAZANIM HESAPLAMA YARDIMCILARI
# ==================================================================
async def kazanimlari_hesapla(komut_turu: str, user_id: int,
                               slot_dolu: bool, slot_kapasite: int) -> dict:
    """Komut turune gore rastgele kazanim hesapla.
    Returns: {esyalar: [{item, amount}], para: int, slot_dolu: bool}
    """
    kazanclar = YAGMA_KAZANIMLAR.get(komut_turu, [])
    para_bilgi = YAGMA_PARA_SANSI.get(komut_turu, (0, (0, 0)))

    envanter_adet = await db.get_inventory_count(user_id)
    slot_var = (envanter_adet < slot_kapasite)

    esyalar = []
    para_kazanclari = 0

    # Esya kazanma sansi
    for k in kazanclar:
        sans = k.get('sans', 0)
        if random.random() < sans:
            esya = k['item']
            miktar = k['miktar']

            if esya == 'Para':
                para_kazanclari += miktar
            elif slot_var:
                # Kapasiteyi asmadan esya ekle.
                kalan_slot = max(0, slot_kapasite - envanter_adet)
                eklenen_miktar = min(miktar, kalan_slot)
                if eklenen_miktar > 0:
                    esyalar.append({'item': esya, 'amount': eklenen_miktar})
                    envanter_adet += eklenen_miktar
                    slot_var = envanter_adet < slot_kapasite

    # Rastgele para sansi
    para_sansi, para_aralik = para_bilgi
    if random.random() < para_sansi:
        para_ekle = random.randint(*para_aralik)
        para_kazanclari += para_ekle

    return {
        'esyalar': esyalar,
        'para': para_kazanclari,
        'slot_dolu': not slot_var
    }


async def harac_kes(saldirgan_id: int, cete_id: int,
                    cete_bilgi: dict, kazanim: dict) -> dict:
    """Bolge sahibi ceteye harac kes.
    Returns: {harac_miktari, harac_turu}
    """
    # Hedef cete bilgisi
    cete_ad = cete_bilgi.get('name', 'Bilinmeyen')

    # Haraç oranı: %10-15 arasi rastgele
    oran = random.uniform(config.HARAC_MIN_ORAN, config.HARAC_MAX_ORAN)

    # Esyalardan harac kes (en fazla 1 esya, 1 adet)
    harac_esya = None
    if kazanim['esyalar']:
        # En dusuk degerli esyayi sec
        # Basit yol: ilk esyayi al
        secim = kazanim['esyalar'][0]
        if secim['amount'] > 0:
            harac_adet = max(1, int(secim['amount'] * oran))
            harac_adet = min(harac_adet, secim['amount'])
            if harac_adet > 0:
                harac_esya = {
                    'item': secim['item'],
                    'amount': harac_adet,
                    'oran': oran
                }
                # Saldirganin kazancindan dus
                secim['amount'] -= harac_adet
                # Cete kasa envanterine ekle
                await db.add_gang_item(cete_id, secim['item'], harac_adet)

    # Para haraci
    para_haraci = int(kazanim['para'] * oran)
    if para_haraci > 0:
        kazanim['para'] -= para_haraci
        await db.update_gang_money(cete_id, para_haraci)

    return {
        'esya': harac_esya,
        'para': para_haraci,
        'cete_adi': cete_ad,
        'oran': oran
    }


# ==================================================================
# COG SINIFI
# ==================================================================
class YagmaCog(commands.Cog):
    """Yagma, arastirma, enfekte temizleme cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # ORTAK YARDIMCI FONKSIYON
    # ==================================================================
    async def _kontroller(self, ctx: commands.Context) -> dict:
        """Ortak kontroller. Hata varsa dict['hata'] dolar.
        Returns: {hata: str | None, user_data, slot_kapasite}
        """
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            return {'hata': MSG_KULLANICI_YOK}
        if user_data.get('gozlemci', 0):
            return {'hata': MSG_GOZLEMCİ_YETKISIZ}
        if user_data.get('is_dead', 0):
            return {'hata': "💀 Karakterin olu. Bu komutu kullanamazsin."}

        # Kanal bir RP kategorisinde mi?
        kanal = ctx.channel
        kategori_id = None
        try:
            kategori_id = kanal.category_id
        except AttributeError:
            pass
        # Thread icindeyse parent kategori
        if kategori_id is None and hasattr(kanal, 'parent') and kanal.parent:
            kategori_id = kanal.parent.category_id

        if kategori_id not in config.RP_KATEGORILERI:
            return {'hata':
                "⚠️ Bu komut sadece RP lokasyon kanallarinda kullanilir "
                "(sehirler, tehlikeli bolgeler, askeri bolgeler vb.)."
            }

        # Bolge kilitli mi?
        locked, reason = await db.is_territory_locked(ctx.channel.id)
        if locked:
            return {'hata': MSG_BOLGE_KILITLI.format(sebep=reason or "Belirtilmemis")}

        # Cooldown (global 3 saat)
        cd_kalan = await db.get_cooldown(ctx.author.id, 'yagma')
        if cd_kalan > 0:
            return {'hata':
                MSG_COOLDOWN_AKTIF.format(kalan_dk=cd_kalan // 60)
            }

        slot_kapasite = await db.get_slot_capacity(ctx.author.id)
        return {
            'hata': None,
            'user_data': user_data,
            'slot_kapasite': slot_kapasite
        }

    async def _uygula(self, ctx: commands.Context, komut_turu: str,
                      baslik: str):
        """Yagma/arastir/enfekte-temizle icin ortak uygulama."""
        kontrol = await self._kontroller(ctx)
        if kontrol['hata']:
            await self._send_error(ctx, kontrol['hata'])
            return

        user_data = kontrol['user_data']
        slot_kapasite = kontrol['slot_kapasite']

        # Bolgenin sahibi cete var mi? (hedef kullanici kendi cetesinden degilse harac)
        bolge_sahibi = await db.get_territory_owner(ctx.channel.id)
        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        harac_bilgi = None

        if bolge_sahibi and (not kullanici_cetesi or
                              kullanici_cetesi.get('gang_id') != bolge_sahibi['gang_id']):
            # Haraç kesilecek
            # Once kazanimi hesapla
            kazanım = await kazanimlari_hesapla(
                komut_turu, ctx.author.id, False, slot_kapasite
            )
            harac_bilgi = await harac_kes(
                ctx.author.id, bolge_sahibi['gang_id'], bolge_sahibi, kazanım
            )
        else:
            kazanım = await kazanimlari_hesapla(
                komut_turu, ctx.author.id, False, slot_kapasite
            )

        # Kazanimlari uygula
        uygulanan_esyalar = []
        for e in kazanım['esyalar']:
            if e['amount'] > 0:
                await db.add_item(ctx.author.id, e['item'], e['amount'])
                uygulanan_esyalar.append(f"• {e['item']} x{e['amount']}")

        if kazanım['para'] > 0:
            await db.update_money(ctx.author.id, kazanım['para'])

        # Cooldown baslat
        await db.set_cooldown(ctx.author.id, 'yagma')

        # Log
        await db.add_action_log('envanter', ctx.author.id, None,
                                 f'{komut_turu}',
                                 {'esyalar': uygulanan_esyalar,
                                  'para': kazanım['para'],
                                  'harac': harac_bilgi is not None})

        # Mesaj olustur
        if uygulanan_esyalar or kazanım['para'] > 0:
            mesaj_parca = []
            if uygulanan_esyalar:
                mesaj_parca.append("**Esyalar:**\n" + "\n".join(uygulanan_esyalar))
            if kazanım['para'] > 0:
                mesaj_parca.append(f"**Para:** {format_para(kazanım['para'])}")

            embed = embeds.success_embed(
                f"{baslik} Basarili",
                "\n\n".join(mesaj_parca)
            )
        else:
            embed = embeds.warning_embed(
                f"{baslik} Bos",
                "Bu bolgede kayda deger bir sey bulamadin."
            )

        # Haraç bilgisi
        if harac_bilgi:
            harac_metin = []
            if harac_bilgi['esya']:
                harac_metin.append(
                    f"• {harac_bilgi['esya']['item']} x{harac_bilgi['esya']['amount']}"
                )
            if harac_bilgi['para'] > 0:
                harac_metin.append(f"• {format_para(harac_bilgi['para'])}")

            embed.add_field(
                name=f"🏴 Bolge Vergisi ({harac_bilgi['cete_adi']})",
                value=(
                    f"Bu bolge **{harac_bilgi['cete_adi']}** cetesi "
                    f"tarafindan kontrol ediliyor. Kazanimin "
                    f"%{int(harac_bilgi['oran'] * 100)}'i harac olarak kesildi:\n"
                    + "\n".join(harac_metin)
                ),
                inline=False
            )

        embed.set_footer(
            text=f"Yagma cooldown: 3 saat | User ID: {ctx.author.id}"
        )
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /yagma
    # ==================================================================
    @commands.hybrid_command(
        name="yagma",
        description="Bulundugun bolgeyi yagmala (3 saat cooldown)"
    )
    async def yagma_slash(self, ctx: commands.Context):
        """Bolgeyi yagmala."""
        await self._uygula(ctx, 'yagma', 'Yagma')

    # ==================================================================
    # /arastir
    # ==================================================================
    @commands.hybrid_command(
        name="arastir",
        description="Bulundugun bolgeyi arastir (3 saat cooldown)"
    )
    async def arastir_slash(self, ctx: commands.Context):
        """Bolgeyi arastir."""
        await self._uygula(ctx, 'arastir', 'Arastirma')

    # ==================================================================
    # /enfekte-temizle
    # ==================================================================
    @commands.hybrid_command(
        name="enfekte-temizle",
        description="Bolgedeki enfekteleri temizle (3 saat cooldown)"
    )
    async def enfekte_temizle_slash(self, ctx: commands.Context):
        """Bolgedeki enfekteleri temizle."""
        await self._uygula(ctx, 'enfekte_temizle', 'Enfekte Temizleme')

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
    await bot.add_cog(YagmaCog(bot))
    logger.info("YagmaCog yuklendi")
