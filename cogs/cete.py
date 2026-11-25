"""
cogs/cete.py - Çete (Fraksiyon) Sistemi
Komutlar: /cete-kur, /cete-bilgi, /cete-kasa, /cete-yatir, /cete-cek,
          /cete-davet, /cete-kabul, /cete-ayril, /cete-bolge-al,
          /cete-baskin, /cete-perkler
Onay bekleyen çete kurulumları admin cog'ından onaylanır.
"""
import logging
import json
import time
import random
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import CETE_PERKLERI
from utils.formatting import format_para, format_sure, format_tarih
from utils.localization import (
    MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
    MSG_CETE_KURULUM_TALEP, MSG_CETE_ZATEN_UYE, MSG_CETE_SINIR_DOLDU,
    MSG_CETE_KASA_YATIRMA, MSG_CETE_KASA_CEKME, MSG_CETE_KASA_YETERSIZ,
    MSG_CETE_KASA_YETKISIZ, MSG_CETE_DAVET_GONDERILDI,
    MSG_CETE_KABUL_EDILDI, MSG_CETE_KAN_BAGISI_YETERSIZ,
    MSG_CETE_BASKIN_ILAN, MSG_CETE_BASKIN_HAZIRLIK,
)


logger = logging.getLogger("tlo.cogs.cete")


# ==================================================================
# CETE KURULUM VIEW (Perk secimi)
# ==================================================================
class PerkSecimView(discord.ui.View):
    """2 perk secmek icin view (checkbox mantigi)."""
    def __init__(self, member: discord.Member, cete_adi: str,
                 cete_turu: str):
        super().__init__(timeout=300)
        self.member = member
        self.cete_adi = cete_adi
        self.cete_turu = cete_turu
        self.secili_perkler = set()

        # Tum perkleri buton olarak ekle (her turde 9 adet, 3x3 grid)
        for perk_id, perk_bilgi in CETE_PERKLERI.items():
            # Tur filtresi
            if cete_turu == "Normal Çete" and "Tarikat Özel" in perk_bilgi['isim']:
                continue
            if cete_turu == "Tarikat Çetesi" and "Normal Çete Özel" in perk_bilgi['isim']:
                continue
            if cete_turu == "Milis Grubu" and (" Özel" in perk_bilgi['isim']):
                continue

            btn = discord.ui.Button(
                label=perk_bilgi['isim'][:70],
                style=discord.ButtonStyle.secondary,
                custom_id=f"perk_{perk_id}",
                row=0
            )
            btn.callback = self._perk_callback
            self.add_item(btn)

        # Onay butonu
        onay_btn = discord.ui.Button(
            label="Talebi Gonder (2 perk secilmeli)",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=4
        )
        onay_btn.callback = self._onay_callback
        self.add_item(onay_btn)

    async def _perk_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True
            )
            return

        # Tiklanan perk ID
        custom_id = interaction.data.get('custom_id', '')
        perk_id = custom_id.replace('perk_', '')

        if perk_id in self.secili_perkler:
            # Zaten secili, kaldir
            self.secili_perkler.remove(perk_id)
            await interaction.response.edit_message(
                content=f"Secili perkler ({len(self.secili_perkler)}/2): " +
                        ", ".join(CETE_PERKLERI[p]['isim'] for p in self.secili_perkler)
                if self.secili_perkler else "Secili perk yok",
                view=self
            )
        else:
            # Yeni secim, max 2 kontrol
            if len(self.secili_perkler) >= 2:
                await interaction.response.send_message(
                    embed=embeds.warning_embed(
                        "Maksimum 2 Perk",
                        "En fazla 2 perk secebilirsin. Once birini kaldir."
                    ),
                    ephemeral=True
                )
                return
            self.secili_perkler.add(perk_id)
            await interaction.response.edit_message(
                content=f"Secili perkler ({len(self.secili_perkler)}/2): " +
                        ", ".join(CETE_PERKLERI[p]['isim'] for p in self.secili_perkler),
                view=self
            )

    async def _onay_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True
            )
            return
        if len(self.secili_perkler) != 2:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Eksik Perk",
                    "Tam olarak 2 perk secmelisin!"
                ),
                ephemeral=True
            )
            return

        # Çete turune gore limit kontrol
        existing_count = await db.count_approved_gangs_by_type(self.cete_turu)
        max_map = {
            "Normal Çete": config.MAX_NORMAL_CETE,
            "Tarikat Çetesi": config.MAX_TARIKAT_CETE,
            "Milis Grubu": config.MAX_MILIS_CETE,
        }
        max_count = max_map.get(self.cete_turu, 0)
        if existing_count >= max_count:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Sinir Doldu",
                    MSG_CETE_SINIR_DOLDU
                ),
                ephemeral=True
            )
            return

        # Çete olustur (approved=0, admin onayi bekler)
        perk_list = list(self.secili_perkler)
        gang_id = await db.create_gang(
            name=self.cete_adi,
            gang_type=self.cete_turu,
            leader_id=self.member.id,
            perks=perk_list
        )

        # Çete kurulum talepleri kanalina bildiri
        talep_kanal = interaction.guild.get_channel(
            config.KANAL_CETE_KURULUM_TALEPLERI
        ) if interaction.guild else None
        if talep_kanal:
            perk_metin = "\n".join(
                f"• **{CETE_PERKLERI[p]['isim']}** - {CETE_PERKLERI[p]['aciklama']}"
                for p in perk_list
            )
            talep_embed = discord.Embed(
                title=f"📋 Çete Kurulum Talebi #{gang_id}",
                description=(
                    f"**Çete Adi:** {self.cete_adi}\n"
                    f"**Tür:** {self.cete_turu}\n"
                    f"**Kurucu:** {self.member.mention}\n\n"
                    f"**Secilen Yetenekler:**\n{perk_metin}"
                ),
                color=config.RENK_CETE,
                timestamp=discord.utils.utcnow()
            )
            talep_embed.set_footer(text=f"Onay icin: /cete-onayla {gang_id}")
            try:
                await talep_kanal.send(embed=talep_embed)
            except Exception as e:
                logger.error(f"cete-talep gonderilemedi: {e}")

        # Çete onay loguna da bildiri
        onay_log = interaction.guild.get_channel(config.KANAL_CETE_ONAY_LOG) if interaction.guild else None
        if onay_log:
            try:
                await onay_log.send(embed=talep_embed)
            except Exception:
                pass

        await interaction.response.edit_message(
            content=None,
            embed=embeds.success_embed(
                "Çete Kurulum Talebi Gonderildi",
                MSG_CETE_KURULUM_TALEP
            ),
            view=None
        )


# ==================================================================
# CETE DAVET VIEW (hedefe gosterilir)
# ==================================================================
class CeteDavetView(discord.ui.View):
    """Cete daveti kabul/red."""
    def __init__(self, hedef: discord.Member, davetci: discord.Member,
                 cete_adi: str):
        super().__init__(timeout=120)
        self.hedef = hedef
        self.davetci = davetci
        self.cete_adi = cete_adi
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


# ==================================================================
# COG SINIFI
# ==================================================================
class CeteCog(commands.Cog):
    """Çete sistemi cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /cete-kur
    # ==================================================================
    @commands.hybrid_command(
        name="cete-kur",
        description="Yeni çete kurma talebi gonderir (admin onayi gerekir)"
    )
    @app_commands.describe(
        isim="Çete adi (RP'ye uygun, kufursuz)",
        tur="Çete türü"
    )
    @app_commands.choices(tur=[
        app_commands.Choice(name="Normal Çete", value="Normal Çete"),
        app_commands.Choice(name="Tarikat Çetesi", value="Tarikat Çetesi"),
        app_commands.Choice(name="Milis Grubu", value="Milis Grubu"),
    ])
    async def cete_kur_slash(self, ctx: commands.Context, isim: str,
                              tur: app_commands.Choice[str]):
        """Çete kurma talebi gonderir."""
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

        # Cete türü meslegi ile uyumlu mu?
        meslek = (user_data.get('meslek') or '').lower()
        cete_turu = tur.value

        if cete_turu == "Normal Çete":
            if not any(x in meslek for x in ['savaşçı', 'haberci', 'stokçu',
                                              'normal çete', 'çete']):
                await self._send_error(ctx,
                    "🚫 Normal Çete kurmak icin Normal Çete meslegine sahip olmaniz gerekir."
                )
                return
        elif cete_turu == "Tarikat Çetesi":
            if not any(x in meslek for x in ['vaiz', 'fedai', 'inisiye',
                                              'tarikat', 'mürşit']):
                await self._send_error(ctx,
                    "🚫 Tarikat Çetesi kurmak icin Tarikat meslegine sahip olmaniz gerekir."
                )
                return
        elif cete_turu == "Milis Grubu":
            # Milis grubu herkes tarafindan kurulabilir
            pass

        # Zaten cete uyesi mi?
        existing_gang = await db.get_user_gang(ctx.author.id)
        if existing_gang:
            await self._send_error(ctx, MSG_CETE_ZATEN_UYE)
            return

        # Cete adi kontrol
        isim = isim.strip()
        if len(isim) < 3 or len(isim) > 40:
            await self._send_error(ctx,
                "Çete adi 3-40 karakter arasinda olmali."
            )
            return

        # Ayni isimde cete var mi?
        existing = await db.get_gang_by_name(isim)
        if existing:
            await self._send_error(ctx,
                f"'{isim}' adinda bir çete zaten var."
            )
            return

        # Cete turu limit kontrol
        existing_count = await db.count_approved_gangs_by_type(cete_turu)
        max_map = {
            "Normal Çete": config.MAX_NORMAL_CETE,
            "Tarikat Çetesi": config.MAX_TARIKAT_CETE,
            "Milis Grubu": config.MAX_MILIS_CETE,
        }
        max_count = max_map.get(cete_turu, 0)
        if existing_count >= max_count:
            await self._send_error(ctx, MSG_CETE_SINIR_DOLDU)
            return

        # Perk secim menusu
        view = PerkSecimView(ctx.author, isim, cete_turu)

        # Tum perkleri goster
        embed = discord.Embed(
            title="✨ Çete Yetenek (Perk) Secimi",
            description=(
                f"**Çete Adi:** {isim}\n"
                f"**Tür:** {cete_turu}\n"
                f"**Kurucu:** {ctx.author.mention}\n\n"
                f"**2 yetenek secin.** Asagidaki butonlardan 2 tanesini tiklayin. "
                f"Secmek icin tiklayin, secimi kaldirmak icin tekrar tiklayin."
            ),
            color=config.RENK_CETE
        )

        # Tum perkleri listele
        for perk_id, perk in CETE_PERKLERI.items():
            # Tur filtresi
            if cete_turu == "Normal Çete" and "Tarikat Özel" in perk['isim']:
                continue
            if cete_turu == "Tarikat Çetesi" and "Normal Çete Özel" in perk['isim']:
                continue
            if cete_turu == "Milis Grubu" and " Özel" in perk['isim']:
                continue
            embed.add_field(
                name=f"✨ {perk['isim']}",
                value=perk['aciklama'],
                inline=False
            )

        await self._send(ctx, embed=embed, view=view)

    # ==================================================================
    # /cete-bilgi
    # ==================================================================
    @commands.hybrid_command(
        name="cete-bilgi",
        description="Çete bilgilerini gosterir"
    )
    @app_commands.describe(
        cete_adi="Çete adi (bos = kendi ceteniz)"
    )
    async def cete_bilgi_slash(self, ctx: commands.Context,
                                cete_adi: str = None):
        """Çete bilgisi gosterir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        # Hedef cete belirle
        gang_data = None
        if cete_adi:
            gang_data = await db.get_gang_by_name(cete_adi)
            if not gang_data:
                await self._send_error(ctx, f"'{cete_adi}' adli çete bulunamadi.")
                return
        else:
            # Kendi cetesi
            kullanici_cetesi = await db.get_user_gang(ctx.author.id)
            if not kullanici_cetesi:
                await self._send_error(ctx, "Bir ceteye uye degilsin.")
                return
            gang_data = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
            if not gang_data:
                await self._send_error(ctx, "Çete bulunamadi.")
                return

        # Çete onayli mi?
        if not gang_data.get('approved', 0):
            await self._send_error(ctx,
                f"Çete **{gang_data['name']}** henuz onaylanmadi. Admin onayi bekleniyor."
            )
            return

        # Uyeleri getir
        members = await db.get_gang_members(gang_data['id'])
        inventory = await db.get_gang_inventory(gang_data['id'])

        # Cete embed'i
        embed = embeds.cete_embed(gang_data, members, inventory)

        # Bölge sayisi
        territories = await db.get_gang_territories(gang_data['id'])
        embed.add_field(
            name="🗺️ Kontrollu Bölgeler",
            value=f"**{len(territories)}** bölge",
            inline=True
        )

        # Kurucu
        leader = self.bot.get_user(gang_data.get('leader_id'))
        if leader:
            embed.add_field(name="👑 Kurucu",
                            value=leader.mention, inline=True)

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /cete-kasa
    # ==================================================================
    @commands.hybrid_command(
        name="cete-kasa",
        description="Cete kasa bakiyesini gosterir"
    )
    async def cete_kasa_slash(self, ctx: commands.Context):
        """Cete kasa bilgisi."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        gang_data = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
        if not gang_data:
            await self._send_error(ctx, "Çete bulunamadi.")
            return

        inventory = await db.get_gang_inventory(gang_data['id'])
        members = await db.get_gang_members(gang_data['id'])

        embed = discord.Embed(
            title=f"💰 Çete Kasası - {gang_data['name']}",
            color=config.RENK_CETE
        )
        embed.add_field(
            name="💵 Nakit",
            value=format_para(gang_data.get('money', 0)),
            inline=False
        )

        if inventory:
            env_liste = "\n".join(f"• {i['item']} x{i['amount']}" for i in inventory)
            embed.add_field(name="📦 Esyalar", value=env_liste, inline=False)
        else:
            embed.add_field(name="📦 Esyalar", value="*Bos*", inline=False)

        embed.add_field(name="👥 Üye Sayisi",
                        value=str(len(members)), inline=True)

        # Pasif gelir bilgisi
        last_income = gang_data.get('passive_income_at', 0) or 0
        gecen = int(time.time()) - last_income
        kalan = config.CETE_PASIF_GELIR_ARALIK - gecen
        if kalan > 0:
            embed.add_field(
                name="💰 Sonraki Pasif Gelir",
                value=format_sure(kalan),
                inline=True
            )
        else:
            embed.add_field(
                name="💰 Pasif Gelir",
                value="Hazir! (Yakinda eklenecek)",
                inline=True
            )

        embed.set_footer(text=f"Çete ID: {gang_data['id']}")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /cete-yatir
    # ==================================================================
    @commands.hybrid_command(
        name="cete-yatir",
        description="Cete kasa para yatirir"
    )
    @app_commands.describe(miktar="Yatirilacak miktar")
    async def cete_yatir_slash(self, ctx: commands.Context, miktar: int):
        """Cete kasaya para yatirir."""
        if miktar <= 0:
            await self._send_error(ctx, "Gecerli bir miktar girin.")
            return

        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        if user_data.get('gozlemci', 0):
            await self._send_error(ctx, MSG_GOZLEMCİ_YETKISIZ)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        if user_data['para'] < miktar:
            await self._send_error(ctx, "Yetersiz bakiye.")
            return

        # Para transferi
        await db.update_money(ctx.author.id, -miktar)
        await db.update_gang_money(kullanici_cetesi['gang_id'], miktar)

        # Log
        await db.add_action_log('cete_kasa', ctx.author.id, None,
                                 'yatirma',
                                 {'miktar': miktar,
                                  'cete_id': kullanici_cetesi['gang_id']})

        # Cete kasa log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_CETE_KASA_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="💰 Çete Kasa - Yatirma",
                description=(
                    f"**Üye:** {ctx.author.mention}\n"
                    f"**Çete:** {kullanici_cetesi.get('name', '?')}\n"
                    f"**Miktar:** {format_para(miktar)}"
                ),
                color=config.RENK_KASA_YATIRMA,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"cete-kasa-log gonderilemedi: {e}")

        await self._send(ctx, embed=embeds.success_embed(
            "Yatirma Basarili",
            MSG_CETE_KASA_YATIRMA.format(miktar=miktar)
        ))

    # ==================================================================
    # /cete-cek
    # ==================================================================
    @commands.hybrid_command(
        name="cete-cek",
        description="Cete kasadan para ceker (sadece lider/subay)"
    )
    @app_commands.describe(miktar="Cekilecek miktar")
    async def cete_cek_slash(self, ctx: commands.Context, miktar: int):
        """Cete kasadan para ceker."""
        if miktar <= 0:
            await self._send_error(ctx, "Gecerli bir miktar girin.")
            return

        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        # Yetki kontrol (lider veya subay)
        if kullanici_cetesi.get('role') not in ('lider', 'subay'):
            await self._send_error(ctx, MSG_CETE_KASA_YETKISIZ)
            return

        gang_data = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
        if not gang_data:
            await self._send_error(ctx, "Çete bulunamadi.")
            return

        if gang_data.get('money', 0) < miktar:
            await self._send_error(ctx, MSG_CETE_KASA_YETERSIZ)
            return

        # Para transferi
        await db.update_gang_money(kullanici_cetesi['gang_id'], -miktar)
        await db.update_money(ctx.author.id, miktar)

        # Log
        await db.add_action_log('cete_kasa', ctx.author.id, None,
                                 'cekme',
                                 {'miktar': miktar,
                                  'cete_id': kullanici_cetesi['gang_id']})

        # Cete kasa log kanalina
        kanal = ctx.guild.get_channel(config.KANAL_CETE_KASA_LOG) if ctx.guild else None
        if kanal:
            log_embed = discord.Embed(
                title="💸 Çete Kasa - Cekme",
                description=(
                    f"**Üye:** {ctx.author.mention}\n"
                    f"**Çete:** {kullanici_cetesi.get('name', '?')}\n"
                    f"**Rol:** {kullanici_cetesi.get('role', '?')}\n"
                    f"**Miktar:** {format_para(miktar)}"
                ),
                color=config.RENK_KASA_CEKME,
                timestamp=discord.utils.utcnow()
            )
            try:
                await kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"cete-kasa-log gonderilemedi: {e}")

        await self._send(ctx, embed=embeds.success_embed(
            "Cekme Basarili",
            MSG_CETE_KASA_CEKME.format(miktar=miktar)
        ))

    # ==================================================================
    # /cete-davet
    # ==================================================================
    @commands.hybrid_command(
        name="cete-davet",
        description="Bir kullanicici ceteye davet eder (lider/subay)"
    )
    @app_commands.describe(hedef="Davet edilecek kullanici")
    async def cete_davet_slash(self, ctx: commands.Context,
                                hedef: discord.Member):
        """Cete daveti gonderir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        # Yetki kontrol
        if kullanici_cetesi.get('role') not in ('lider', 'subay'):
            await self._send_error(ctx, "Sadece lider ve subaylar davet gonderebilir.")
            return

        if hedef.id == ctx.author.id:
            await self._send_error(ctx, "Kendini davet edemezsin.")
            return

        hedef_data = await db.get_user(hedef.id)
        if not hedef_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if hedef_data.get('gozlemci', 0):
            await self._send_error(ctx, "Gozlemciler davet edilemez.")
            return

        # Zaten bir cetede mi?
        existing = await db.get_user_gang(hedef.id)
        if existing:
            await self._send_error(ctx,
                f"{hedef.mention} zaten bir ceteye uye.")
            return

        gang_data = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
        if not gang_data:
            await self._send_error(ctx, "Çete bulunamadi.")
            return

        # Davet gonder
        view = CeteDavetView(hedef, ctx.author, gang_data['name'])
        embed = discord.Embed(
            title="📨 Çete Daveti",
            description=(
                f"{hedef.mention}, **{gang_data['name']}** "
                f"({gang_data['type']}) cetesi tarafindan davet edildin!\n"
                f"**Davetci:** {ctx.author.mention}\n\n"
                f"Kabul edersen **{config.CETE_KAN_BAGI_PARA} 🪙** kan bagisi "
                f"odemen gerekir."
            ),
            color=config.RENK_CETE
        )
        embed.set_footer(text="120 saniye icinde yanit ver.")
        await self._send(ctx, content=hedef.mention, embed=embed, view=view)

        # Bekle
        await view.wait()

        if view.sonuc != 'kabul':
            await self._send(ctx, 
                embed=embeds.warning_embed(
                    "Davet Reddedildi",
                    f"{hedef.mention} daveti reddetti veya yanit vermedi."
                )
            )
            return

        # Kabul etti - kan bagisi kontrol
        if hedef_data['para'] < config.CETE_KAN_BAGI_PARA:
            await self._send(ctx, 
                embed=embeds.error_embed(
                    "Kan Bagisi Yetersiz",
                    MSG_CETE_KAN_BAGISI_YETERSIZ.format(
                        ucret=config.CETE_KAN_BAGI_PARA
                    )
                )
            )
            return

        # Cete uyesi ekle
        eklendi = await db.add_gang_member(
            kullanici_cetesi['gang_id'], hedef.id
        )
        if not eklendi:
            await self._send_error(ctx,
                f"{hedef.mention} eklenemedi (zaten uye olabilir).")
            return

        # Kan bagisi kes
        await db.update_money(hedef.id, -config.CETE_KAN_BAGI_PARA)
        await db.update_gang_money(
            kullanici_cetesi['gang_id'], config.CETE_KAN_BAGI_PARA
        )

        # Hedefe cete rolunu ver
        uye_rol_id = config.CETE_UYE_ROLLERI.get(gang_data['type'])
        if uye_rol_id:
            uye_rol = ctx.guild.get_role(uye_rol_id)
            if uye_rol and uye_rol not in hedef.roles:
                try:
                    await hedef.add_roles(uye_rol, reason="Çete uyeligi")
                except discord.Forbidden:
                    pass

        # Log
        await db.add_action_log('cete_kasa', hedef.id, None,
                                 'kan_bagisi',
                                 {'cete_id': kullanici_cetesi['gang_id'],
                                  'para': config.CETE_KAN_BAGI_PARA})

        await self._send(ctx, embed=embeds.success_embed(
            "Çeteye Katildi",
            MSG_CETE_KABUL_EDILDI.format(ucret=config.CETE_KAN_BAGI_PARA)
        ))

    # ==================================================================
    # /cete-ayril
    # ==================================================================
    @commands.hybrid_command(
        name="cete-ayril",
        description="Ceteden ayrilir"
    )
    async def cete_ayril_slash(self, ctx: commands.Context):
        """Ceteden ayrilir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        # Lider ayrilamaz (once devretmeli veya feshettirmeli)
        if kullanici_cetesi.get('role') == 'lider':
            await self._send_error(ctx,
                "Lider olarak ayrilamazsin. Once liderligi devret "
                "veya admin ile gorusup cete feshini talep et."
            )
            return

        gang_data = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
        cete_rol_id = config.CETE_UYE_ROLLERI.get(
            gang_data.get('type') if gang_data else None
        )
        if cete_rol_id:
            cete_rol = ctx.guild.get_role(cete_rol_id)
            if cete_rol and cete_rol in ctx.author.roles:
                try:
                    await ctx.author.remove_roles(cete_rol, reason="Ceteden ayrilma")
                except discord.Forbidden:
                    pass

        await db.leave_gang(ctx.author.id)

        await self._send(ctx, embed=embeds.success_embed(
            "Ayrildi",
            f"**{gang_data['name'] if gang_data else '?'}** cetesinden ayrildin."
        ))

    # ==================================================================
    # /cete-bolge-al
    # ==================================================================
    @commands.hybrid_command(
        name="cete-bolge-al",
        description="Bulundugun bolgeyi ceteniz icin kontrol altina alir"
    )
    async def cete_bolge_al_slash(self, ctx: commands.Context):
        """Bolge kontrolunu alir."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        # Yetki (lider veya subay)
        if kullanici_cetesi.get('role') not in ('lider', 'subay'):
            await self._send_error(ctx,
                "Sadece lider ve subaylar bolge alabilir."
            )
            return

        # Kanal bir RP kategorisinde mi?
        kanal = ctx.channel
        kategori_id = kanal.category_id
        if kategori_id not in config.RP_KATEGORILERI:
            await self._send_error(ctx,
                "Bu komut sadece RP lokasyon kanallarinda kullanilir."
            )
            return

        # Bolge zaten birinin mi?
        existing_owner = await db.get_territory_owner(ctx.channel.id)
        if existing_owner:
            if existing_owner['gang_id'] == kullanici_cetesi['gang_id']:
                await self._send_error(ctx,
                    "Bu bolge zaten sizin cetenizin kontrolunde."
                )
                return
            await self._send_error(ctx,
                f"Bu bolge zaten **{existing_owner['name']}** cetesi tarafindan kontrol ediliyor. "
                f"Bolgeyi almak icin baskin yapmalisiniz."
            )
            return

        # Bolgeyi al
        await db.set_territory_owner(ctx.channel.id, kullanici_cetesi['gang_id'])

        # Kanal basligini guncelle
        try:
            new_topic = f"🏴 Kontrol: {gang_data['name'] if (gang_data := await db.get_gang_by_id(kullanici_cetesi['gang_id'])) else '?'}"
            await kanal.edit(topic=new_topic)
        except discord.Forbidden:
            pass

        await self._send(ctx, embed=embeds.success_embed(
            "Bolge Alindi",
            f"**{ctx.channel.mention}** bolgesi cetenizin kontrolune gecti.\n"
            f"Bu bolgede yagma/arastirma yapan rakip oyunculardan harac kesilebilir."
        ))

    # ==================================================================
    # /cete-perkler
    # ==================================================================
    @commands.hybrid_command(
        name="cete-perkler",
        description="Tum cete yeteneklerini (perk) listeler"
    )
    async def cete_perkler_slash(self, ctx: commands.Context):
        """Perk listesi."""
        embed = discord.Embed(
            title="✨ Çete Yetenekleri (Perk'ler)",
            description=(
                "Çete kurarken 2 perk secmek zorunludur.\n"
                "Her perk kucuk ama RP'yi etkileyen bonuslar verir."
            ),
            color=config.RENK_CETE
        )

        for perk_id, perk in CETE_PERKLERI.items():
            embed.add_field(
                name=f"✨ {perk['isim']}",
                value=perk['aciklama'],
                inline=False
            )

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /cete-baskin
    # ==================================================================
    @commands.hybrid_command(
        name="cete-baskin",
        description="Baska bir cetenin bolgesine baskin ilan eder"
    )
    @app_commands.describe(
        hedef_cete="Baskin yapilacak cete",
        bolge_kanal="Baskin yapilacak bolge kanali"
    )
    async def cete_baskin_slash(self, ctx: commands.Context,
                                  hedef_cete: str, bolge_kanal: discord.TextChannel):
        """Baskin ilan eder."""
        user_data = await db.get_user(ctx.author.id)
        if not user_data:
            await self._send_error(ctx, MSG_KULLANICI_YOK)
            return

        kullanici_cetesi = await db.get_user_gang(ctx.author.id)
        if not kullanici_cetesi:
            await self._send_error(ctx, "Bir ceteye uye degilsin.")
            return

        # Yetki (lider)
        if kullanici_cetesi.get('role') != 'lider':
            await self._send_error(ctx, "Sadece lider baskin ilan edebilir.")
            return

        # Hedef cete
        hedef_gang = await db.get_gang_by_name(hedef_cete)
        if not hedef_gang:
            await self._send_error(ctx, f"'{hedef_cete}' adli cete bulunamadi.")
            return

        if hedef_gang['id'] == kullanici_cetesi['gang_id']:
            await self._send_error(ctx, "Kendi cetenize baskin yapamazsiniz.")
            return

        # Bolge kontrol
        territory = await db.get_territory_owner(bolge_kanal.id)
        if not territory or territory['gang_id'] != hedef_gang['id']:
            await self._send_error(ctx,
                f"{bolge_kanal.mention} bolgesi {hedef_cete} cetesinin degil."
            )
            return

        # Ayni bolge icin birden fazla paralel baskin olusturulmasin.
        active_raid = await db.get_active_raid(bolge_kanal.id)
        if active_raid:
            await self._send_error(
                ctx,
                "Bu bolgede zaten devam eden bir baskin hazirligi var."
            )
            return

        # Cephane ve ilac maliyeti (baskin icin)
        saldirgan_gang = await db.get_gang_by_id(kullanici_cetesi['gang_id'])
        cep_maliyet = 5  # 5x 9mm Mermi
        ilac_maliyet = 2  # 2x Antibiyotik

        # Cephane kontrolu
        gang_inv = await db.get_gang_inventory(kullanici_cetesi['gang_id'])
        gang_inv_dict = {i['item']: i['amount'] for i in gang_inv}
        if gang_inv_dict.get("9mm Mermi", 0) < cep_maliyet:
            await self._send_error(ctx,
                f"Baskin icin **{cep_maliyet} adet 9mm Mermi** gerekir. "
                f"Çete kasa envanterinde yetersiz."
            )
            return

        # Maliyetleri kes
        await db.remove_gang_item(
            kullanici_cetesi['gang_id'], "9mm Mermi", cep_maliyet
        )

        # Baskin olustur (12 saat hazirlik)
        hazirlik_sure = config.CETE_BASKIN_HAZIRLIK_SAAT * 3600
        raid_id = await db.create_raid(
            attacker_gang=kullanici_cetesi['gang_id'],
            defender_gang=hedef_gang['id'],
            channel_id=bolge_kanal.id,
            duration=hazirlik_sure
        )

        # Bolge-savaslari kanalina bildiri
        savas_kanal = ctx.guild.get_channel(config.KANAL_BOLGE_SAVASLARI) if ctx.guild else None
        if savas_kanal:
            savas_embed = discord.Embed(
                title="⚔️ Baskin Ilani",
                description=MSG_CETE_BASKIN_ILAN.format(
                    saldiran=saldirgan_gang['name'],
                    savunan=hedef_gang['name']
                ),
                color=config.RENK_HATA,
                timestamp=discord.utils.utcnow()
            )
            savas_embed.add_field(
                name="📍 Bolge",
                value=bolge_kanal.mention,
                inline=True
            )
            savas_embed.add_field(
                name="⏰ Hazirlik Suresi",
                value=format_sure(hazirlik_sure),
                inline=True
            )
            savas_embed.add_field(
                name="💰 Maliyet",
                value=f"{cep_maliyet}x 9mm Mermi",
                inline=True
            )
            savas_embed.set_footer(text=f"Baskin ID: {raid_id}")
            try:
                await savas_kanal.send(
                    content=f"@everyone",
                    embed=savas_embed,
                    allowed_mentions=discord.AllowedMentions.all()
                )
            except Exception as e:
                logger.error(f"bolge-savaslari gonderilemedi: {e}")

        await self._send(ctx, embed=embeds.success_embed(
            "Baskin Ilan Edildi",
            f"**{hedef_cete}** cetesinin **{bolge_kanal.mention}** bolgesine "
            f"baskin ilan edildi.\n"
            f"Hazirlik suresi: **{format_sure(hazirlik_sure)}**\n"
            f"Savas suresi dolunca otomatik sonuc aciklanacak."
        ))

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
    await bot.add_cog(CeteCog(bot))
    logger.info("CeteCog yuklendi")
