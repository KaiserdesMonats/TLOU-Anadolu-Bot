"""
cogs/admin.py - Yonetici (Admin) Araclari
Komutlar: /admin-iyilestir, /admin-enfeksiyon-sifirla, /admin-envanter-ekle,
          /admin-karakter-sifirla, /karakter-incele, /log-cek,
          /bolge-kilitle, /bolge-ac, /cete-onayla, /cete-reddet,
          /cete-feshet, /hava-durumu-degistir
Tum admin islemleri gizli log kanalina duser.
"""

import logging
import time
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.checks import is_admin, is_rp_yetkili
from utils.constants import HAVA_DURUMLARI, ITEMS
from utils.formatting import format_para, format_sure, format_tarih
from utils.localization import (
    MSG_ADMIN_IYILESTIR,
    MSG_ADMIN_ENFEKSIYON_SIFIRLA,
    MSG_ADMIN_ENVANTER_EKLE,
    MSG_ADMIN_KARAKTER_SIFIRLA_ONAY,
    MSG_ADMIN_KARAKTER_SIFIRLA_IPTAL,
    MSG_ADMIN_KARAKTER_SIFIRLA_BASARILI,
    MSG_ADMIN_CETE_ONAYLA,
    MSG_ADMIN_CETE_RED,
    MSG_ADMIN_CETE_FESHET,
    MSG_ADMIN_BOLGE_KILITLE,
    MSG_ADMIN_BOLGE_ACILDI,
    MSG_ADMIN_LOG_YOK,
)


logger = logging.getLogger("tlo.cogs.admin")


# ==================================================================
# KARAKTER SIFIRLAMA ONAY VIEW
# ==================================================================
class KarakterSifirlaOnayView(discord.ui.View):
    """Karakter sifirlama icin 2 asamali onay."""

    def __init__(self, admin: discord.Member, hedef: discord.Member):
        super().__init__(timeout=30)
        self.admin = admin
        self.hedef = hedef
        self.onaylandi = False

    @discord.ui.button(
        label="Evet, Sifirla", emoji="⚠️", style=discord.ButtonStyle.danger
    )
    async def evet_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.admin.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True,
            )
            return
        self.onaylandi = True
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="Iptal Et", emoji="❌", style=discord.ButtonStyle.secondary
    )
    async def iptal_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.admin.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin icin degil."),
                ephemeral=True,
            )
            return
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)


# ==================================================================
# COG SINIFI
# ==================================================================
class AdminCog(commands.Cog):
    """Admin komutlari cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Karakter sifirlama beklemede olanlar
        self._sifirlama_bekleyen = {}  # hedef_id -> (admin_id, timestamp)

    # ==================================================================
    # YARDIMCI: Admin log gonderme
    # ==================================================================
    async def _admin_log(
        self,
        guild: discord.Guild,
        action: str,
        admin: discord.Member,
        hedef: discord.Member = None,
        details: str = "",
    ):
        """Admin log kanalina mesaj gonder."""
        kanal = guild.get_channel(config.KANAL_ADMIN_LOG) if guild else None
        if not kanal:
            return
        embed = discord.Embed(
            title=f"🔧 Admin Islemi: {action}",
            description=details,
            color=config.RENK_BILGI,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="🛡️ Admin", value=admin.mention, inline=True)
        if hedef:
            embed.add_field(name="🎯 Hedef", value=hedef.mention, inline=True)
        embed.set_footer(text=f"Admin ID: {admin.id}")
        try:
            await kanal.send(embed=embed)
        except Exception as e:
            logger.error(f"admin-log gonderilemedi: {e}")

    # ==================================================================
    # /admin-iyilestir
    # ==================================================================
    @commands.hybrid_command(
        name="admin-iyilestir",
        description="[Admin] Oyuncunun can/acluk/susuzluk barlarini %100'e cekar",
    )
    @app_commands.describe(hedef="Iyilestirilecek kullanici")
    async def admin_iyilestir_slash(self, ctx: commands.Context, hedef: discord.Member):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        await db.update_stats(hedef.id, can=100, acluk=100, susuzluk=100)

        await db.add_action_log("admin", ctx.author.id, hedef.id, "iyilestir", {})

        await self._admin_log(
            ctx.guild,
            "Iyilestirme",
            ctx.author,
            hedef,
            "Can, Acluk, Susuzluk %100'e cekildi.",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Iyilestirme Basarili",
                MSG_ADMIN_IYILESTIR.format(kullanici=hedef.mention),
            )
        )

    # ==================================================================
    # /admin-enfeksiyon-sifirla
    # ==================================================================
    @commands.hybrid_command(
        name="admin-enfeksiyon-sifirla",
        description="[Admin] Oyuncunun enfeksiyonunu temizler",
    )
    @app_commands.describe(hedef="Enfeksiyonu temizlenecek kullanici")
    async def admin_enfeksiyon_sifirla_slash(
        self, ctx: commands.Context, hedef: discord.Member
    ):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        durum = await db.get_enfeksiyon_durumu(hedef.id)
        if not durum["var"]:
            await self._send_error(ctx, f"{hedef.mention} zaten enfekte degil.")
            return

        await db.clear_enfeksiyon(hedef.id)

        await db.add_action_log(
            "admin",
            ctx.author.id,
            hedef.id,
            "enfeksiyon_sifirla",
            {"onceki_seviye": durum["seviye"]},
        )

        # Enfeksiyon log kanalina da bildiri
        enf_log = (
            ctx.guild.get_channel(config.KANAL_ENFEKSIYON_LOG) if ctx.guild else None
        )
        if enf_log:
            log_embed = discord.Embed(
                title="🛡️ Admin Enfeksiyon Sifirlama",
                description=(
                    f"**Admin:** {ctx.author.mention}\n"
                    f"**Hedef:** {hedef.mention}\n"
                    f"**Onceki Asama:** {durum['seviye']}/4\n"
                    f"**Sonuc:** Enfeksiyon tamamen temizlendi"
                ),
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await enf_log.send(embed=log_embed)
            except Exception:
                pass

        await self._admin_log(
            ctx.guild,
            "Enfeksiyon Sifirlama",
            ctx.author,
            hedef,
            f"Onceki asama: {durum['seviye']}/4",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Enfeksiyon Temizlendi",
                MSG_ADMIN_ENFEKSIYON_SIFIRLA.format(kullanici=hedef.mention),
            )
        )

    # ==================================================================
    # /admin-envanter-ekle
    # ==================================================================
    @commands.hybrid_command(
        name="admin-envanter-ekle",
        description="[Admin] Oyuncunun envanterine esya ekler",
    )
    @app_commands.describe(
        hedef="Hedef kullanici", esya="Esya adi", miktar="Miktar (varsayilan: 1)"
    )
    async def admin_envanter_ekle_slash(
        self, ctx: commands.Context, hedef: discord.Member, esya: str, miktar: int = 1
    ):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        if miktar <= 0:
            await self._send_error(ctx, "Miktar 0'dan buyuk olmali.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        await db.add_item(hedef.id, esya, miktar)

        await db.add_action_log(
            "admin",
            ctx.author.id,
            hedef.id,
            "envanter_ekle",
            {"esya": esya, "miktar": miktar},
        )

        # Envanter log
        env_log = (
            ctx.guild.get_channel(config.KANAL_ENVANTER_LOG) if ctx.guild else None
        )
        if env_log:
            log_embed = discord.Embed(
                title="🛡️ Admin Envanter Ekleme",
                description=(
                    f"**Admin:** {ctx.author.mention}\n"
                    f"**Hedef:** {hedef.mention}\n"
                    f"**Esya:** {esya}\n"
                    f"**Miktar:** {miktar}"
                ),
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await env_log.send(embed=log_embed)
            except Exception:
                pass

        await self._admin_log(
            ctx.guild, "Envanter Ekleme", ctx.author, hedef, f"Esya: {esya} x{miktar}"
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Esya Eklendi",
                MSG_ADMIN_ENVANTER_EKLE.format(
                    kullanici=hedef.mention, esya=esya, miktar=miktar
                ),
            )
        )

    @admin_envanter_ekle_slash.autocomplete("esya")
    async def envanter_ekle_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """Esya adi icin autocomplete - ITEMS listesinden oneriler."""
        choices = []
        for name in ITEMS.keys():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
            if len(choices) >= 25:
                break
        return choices

    # ==================================================================
    # /admin-karakter-sifirla (2 asamali onay)
    # ==================================================================
    @commands.hybrid_command(
        name="admin-karakter-sifirla",
        description="[Admin] Oyuncunun tum ilerlemesini sifirlar (2 asamali onay)",
    )
    @app_commands.describe(hedef="Sifirlanacak kullanici")
    async def admin_karakter_sifirla_slash(
        self, ctx: commands.Context, hedef: discord.Member
    ):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        # 2 asamali onay view
        view = KarakterSifirlaOnayView(ctx.author, hedef)

        embed = embeds.warning_embed(
            "⚠️ Karakter Sifirlama Onayi",
            MSG_ADMIN_KARAKTER_SIFIRLA_ONAY.format(kullanici=hedef.mention),
        )
        embed.add_field(
            name="📋 Silinecek Veriler",
            value=(
                "• Isim, Soyisim, Yas\n"
                "• Sehir, Meslek\n"
                "• Para (100'e sifirlanir)\n"
                "• Tum envanter\n"
                "• Enfeksiyon durumu\n"
                "• Slot seviyesi\n"
                "• Çete uyeligi"
            ),
            inline=False,
        )
        embed.set_footer(text="30 saniye icinde onaylamazsaniz islem iptal edilir.")

        await self._send(ctx, embed=embed, view=view)

        # Bekle
        await view.wait()

        if not view.onaylandi:
            await self._send(ctx, 
                embed=embeds.error_embed(
                    "Islem Iptal Edildi", MSG_ADMIN_KARAKTER_SIFIRLA_IPTAL
                )
            )
            return

        # Onaylandi - sifirla
        await db.admin_reset_character(hedef.id)
        logger.info(f"Karakter DB sifirlandi: {hedef.id}")

        # Rollerden temizle - daha kapsamli
        try:
            # Tüm meslek/şehir/çete rollerini topla
            tum_rol_idleri = set()

            # Şehir rolleri
            tum_rol_idleri.update(config.SEHIR_ROLLERI.values())

            # Meslek grupları (Valilik, Askeri, Polis, Çiftçi, Tamirci, Doktor, Çete, Tarikat, Milis)
            for grup in config.MESLEK_GRUPLARI.values():
                for _, rol_id in grup:
                    tum_rol_idleri.add(rol_id)

            # Çete lider rolleri
            tum_rol_idleri.update(config.CETE_LIDER_ROLLERI.values())

            # Çete üye rolleri
            tum_rol_idleri.update(config.CETE_UYE_ROLLERI.values())

            # Kullanıcının sahip olduğu rolleri bul
            kaldirilacak_roller = []
            for rol_id in tum_rol_idleri:
                rol = ctx.guild.get_role(rol_id)
                if rol and rol in hedef.roles:
                    kaldirilacak_roller.append(rol)

            # Üye rolünü de al
            uye_rol = ctx.guild.get_role(config.ROL_UYE)
            if uye_rol and uye_rol in hedef.roles:
                kaldirilacak_roller.append(uye_rol)
                logger.info(f"Üye rolü bulundu: {uye_rol.name}")
            else:
                logger.warning(f"Üye rolü bulunamadı veya kullanıcıda yok (ID: {config.ROL_UYE})")

            # Tüm rolleri tek seferde kaldır
            if kaldirilacak_roller:
                try:
                    await hedef.remove_roles(*kaldirilacak_roller, reason="Karakter sifirlama")
                    logger.info(f"Karakter sifirlama: {len(kaldirilacak_roller)} rol alindi (user: {hedef.id})")
                except discord.Forbidden:
                    logger.error(f"Rolleri almaya yetkim yok (Forbidden) - Bot rolü üstte mi?")
                except Exception as e:
                    logger.error(f"Rol alma hatasi: {e}")
            else:
                logger.info(f"Kullanıcıda kaldırılacak rol bulunamadı: {hedef.id}")

            # Kayitsiz rolunu geri ver
            kayitsiz = ctx.guild.get_role(config.ROL_KAYITSIZ)
            if kayitsiz is None:
                logger.error(f"Kayıtsız rolü bulunamadı! (ID: {config.ROL_KAYITSIZ})")
            elif kayitsiz in hedef.roles:
                logger.info("Kullanıcıda zaten Kayıtsız rolü var")
            else:
                try:
                    await hedef.add_roles(kayitsiz, reason="Karakter sifirlama")
                    logger.info(f"Kayıtsız rolü verildi: {hedef.id}")
                except discord.Forbidden:
                    logger.error("Kayitsiz rolu verilemedi (Forbidden) - Bot yetkisi yetersiz")
                except Exception as e:
                    logger.error(f"Kayıtsız rolü verme hatası: {e}")

            # Nick sifirla
            try:
                await hedef.edit(nick=None, reason="Karakter sifirlama")
                logger.info(f"Nick sıfırlandı: {hedef.id}")
            except discord.Forbidden:
                logger.warning("Nick değiştirilemedi (Forbidden)")
            except Exception as e:
                logger.warning(f"Nick degistirilemedi: {e}")
        except Exception as e:
            logger.error(f"Rol temizleme hatasi: {e}")

        await self._admin_log(
            ctx.guild,
            "Karakter Sifirlama",
            ctx.author,
            hedef,
            "Tum ilerleme silindi, Kayitsiz statune dondu.",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Karakter Sifirlandi",
                MSG_ADMIN_KARAKTER_SIFIRLA_BASARILI.format(kullanici=hedef.mention),
            )
        )

    # ==================================================================
    # /karakter-incele (God Eye)
    # ==================================================================
    @commands.hybrid_command(
        name="karakter-incele", description="[Admin] Oyuncunun tum verilerini gosterir"
    )
    @app_commands.describe(hedef="Incelenecek kullanici")
    async def karakter_incele_slash(self, ctx: commands.Context, hedef: discord.Member):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        inventory = await db.get_inventory(hedef.id)
        gang = await db.get_user_gang(hedef.id)
        enfeksiyon = await db.get_enfeksiyon_durumu(hedef.id)
        slot_capacity = await db.get_slot_capacity(hedef.id)

        embed = discord.Embed(
            title=f"👁️ Karakter Inceleme - {hedef.display_name}",
            color=config.RENK_PROFIL,
        )
        if hedef.display_avatar:
            embed.set_thumbnail(url=hedef.display_avatar.url)

        # Temel bilgiler
        isim = user_data.get("isim", "?")
        soyisim = user_data.get("soyisim", "") or ""
        tam_isim = f"{isim} {soyisim}".strip()
        embed.add_field(name="📝 Isim", value=tam_isim, inline=True)
        embed.add_field(
            name="🎂 Yas", value=str(user_data.get("yas", "?")), inline=True
        )
        embed.add_field(name="🌍 Sehir", value=user_data.get("sehir", "?"), inline=True)

        embed.add_field(
            name="💼 Meslek", value=user_data.get("meslek", "?"), inline=True
        )
        embed.add_field(
            name="👁️ Gozlemci",
            value="Evet" if user_data.get("gozlemci") else "Hayir",
            inline=True,
        )
        embed.add_field(
            name="💀 Olu",
            value="Evet" if user_data.get("is_dead") else "Hayir",
            inline=True,
        )

        # Stats
        embed.add_field(name="❤️ Can", value=str(user_data.get("can", 0)), inline=True)
        embed.add_field(
            name="🍖 Acluk", value=str(user_data.get("acluk", 0)), inline=True
        )
        embed.add_field(
            name="💧 Susuzluk", value=str(user_data.get("susuzluk", 0)), inline=True
        )

        embed.add_field(
            name="💰 Para", value=format_para(user_data.get("para", 0)), inline=True
        )
        embed.add_field(
            name="🎒 Slot Seviye",
            value=str(user_data.get("slot_seviye", 0)),
            inline=True,
        )
        embed.add_field(
            name="📦 Envanter Dolu",
            value=f"{sum(i['amount'] for i in inventory)}/{slot_capacity}",
            inline=True,
        )

        # Enfeksiyon
        if enfeksiyon["var"]:
            sev = enfeksiyon["seviye"]
            asama_ad = config.ENFEKSIYON_ASAMA_ISIMLERI.get(sev, "?")
            kalan = format_sure(enfeksiyon["kalan_sure"])
            embed.add_field(
                name="🦠 Enfeksiyon",
                value=f"Asama: {sev}/4 ({asama_ad})\nKalan: {kalan}",
                inline=False,
            )
        else:
            embed.add_field(name="🦠 Enfeksiyon", value="✅ Temiz", inline=False)

        # Çete
        if gang:
            embed.add_field(
                name="🏴 Çete",
                value=f"**{gang.get('name', '?')}** ({gang.get('type', '?')})\n"
                f"Rol: {gang.get('role', 'uye')}",
                inline=False,
            )
        else:
            embed.add_field(name="🏴 Çete", value="*Cetesi yok*", inline=False)

        # Envanter
        if inventory:
            env_liste = "\n".join(
                f"• {i['item']} x{i['amount']}" for i in inventory[:15]
            )
            if len(inventory) > 15:
                env_liste += f"\n... ve {len(inventory) - 15} esya daha"
            embed.add_field(name="🎒 Envanter", value=env_liste, inline=False)
        else:
            embed.add_field(name="🎒 Envanter", value="*Bos*", inline=False)

        # Kayit tarihi
        kayit = user_data.get("kayit_tarihi")
        if kayit:
            embed.add_field(
                name="📅 Kayit Tarihi", value=format_tarih(kayit), inline=False
            )

        embed.set_footer(text=f"User ID: {hedef.id}")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /log-cek
    # ==================================================================
    @commands.hybrid_command(
        name="log-cek", description="[Admin] Belirli turde log kayitlarini getirir"
    )
    @app_commands.describe(tur="Log turu", limit="Kac kayit getirilecek (max 50)")
    @app_commands.choices(
        tur=[
            app_commands.Choice(name="📦 Envanter Transferleri", value="envanter"),
            app_commands.Choice(name="💰 Çete Kasa", value="cete_kasa"),
            app_commands.Choice(name="🦠 Enfeksiyon", value="enfeksiyon"),
            app_commands.Choice(name="🛡️ Admin Islemleri", value="admin"),
            app_commands.Choice(name="💼 Meslek Eylemleri", value="meslek"),
            app_commands.Choice(name="🦹 Yankesicilik", value="yankesicilik"),
        ]
    )
    async def log_cek_slash(
        self, ctx: commands.Context, tur: app_commands.Choice[str], limit: int = 20
    ):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        if limit > 50:
            limit = 50
        if limit <= 0:
            limit = 20

        logs = await db.get_logs(tur.value, limit=limit)

        if not logs:
            await self._send(ctx, embed=embeds.info_embed("Log Kaydi", MSG_ADMIN_LOG_YOK))
            return

        embed = discord.Embed(
            title=f"📋 Log Kayitlari - {tur.name}",
            description=f"Son {len(logs)} kayit:",
            color=config.RENK_BILGI,
        )

        for i, log in enumerate(logs[:20]):
            actor_id = log.get("actor_id")
            target_id = log.get("target_id")
            action = log.get("action", "?")
            ts = log.get("timestamp", 0)

            # Timestamp formatla
            try:
                tarih = f"<t:{ts}:R>"
            except Exception:
                tarih = "??"

            satir = f"**{i + 1}.** {tarih}\n"
            satir += f"   🛡️ {f'<@{actor_id}>' if actor_id else 'System'}\n"
            if target_id:
                satir += f"   🎯 <@{target_id}>\n"
            satir += f"   ⚙️ {action}"

            if i < 20:
                embed.add_field(name="\u200b", value=satir, inline=False)

        embed.set_footer(text=f"Toplam {len(logs)} kayit gosterildi")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # /bolge-kilitle
    # ==================================================================
    @commands.hybrid_command(
        name="bolge-kilitle",
        description="[RP Yetkilisi/Admin] Bir bolgeyi gecici olarak kilitler",
    )
    @app_commands.describe(kanal="Kilitlenecek kanal", sebep="Kilitleme sebebi")
    async def bolge_kilitle_slash(
        self, ctx: commands.Context, kanal: discord.TextChannel, sebep: str
    ):
        if not is_rp_yetkili(ctx.author):
            await self._send_error(
                ctx, "🚫 Bu komutu sadece RP Yetkilisi ve Admin kullanabilir."
            )
            return

        await db.lock_territory(kanal.id, sebep)

        # Kanal topic guncelle
        try:
            await kanal.edit(topic=f"🔒 KİLİTLİ: {sebep}")
        except discord.Forbidden:
            pass

        await db.add_action_log(
            "admin",
            ctx.author.id,
            None,
            "bolge_kilitle",
            {"kanal": kanal.id, "sebep": sebep},
        )

        await self._admin_log(
            ctx.guild,
            "Bolge Kilitleme",
            ctx.author,
            None,
            f"Kanal: {kanal.mention}\nSebep: {sebep}",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Bolge Kilitlendi", MSG_ADMIN_BOLGE_KILITLE.format(sebep=sebep)
            )
        )

    # ==================================================================
    # /bolge-ac
    # ==================================================================
    @commands.hybrid_command(
        name="bolge-ac",
        description="[RP Yetkilisi/Admin] Kilitli bolgenin kilidini acar",
    )
    @app_commands.describe(kanal="Acilacak kanal")
    async def bolge_ac_slash(self, ctx: commands.Context, kanal: discord.TextChannel):
        if not is_rp_yetkili(ctx.author):
            await self._send_error(
                ctx, "🚫 Bu komutu sadece RP Yetkilisi ve Admin kullanabilir."
            )
            return

        locked, _ = await db.is_territory_locked(kanal.id)
        if not locked:
            await self._send_error(ctx, "Bu bolge zaten kilitli degil.")
            return

        await db.unlock_territory(kanal.id)

        # Kanal topic temizle
        try:
            await kanal.edit(topic=None)
        except discord.Forbidden:
            pass

        await db.add_action_log(
            "admin", ctx.author.id, None, "bolge_ac", {"kanal": kanal.id}
        )

        await self._admin_log(
            ctx.guild, "Bolge Kilidi Acma", ctx.author, None, f"Kanal: {kanal.mention}"
        )

        await self._send(ctx, 
            embed=embeds.success_embed("Bolge Acildi", MSG_ADMIN_BOLGE_ACILDI)
        )

    # ==================================================================
    # /cete-onayla
    # ==================================================================
    @commands.hybrid_command(
        name="cete-onayla",
        description="[Admin] Beklemedeki çete kurulum talebini onaylar",
    )
    @app_commands.describe(cete_id="Çete ID veya adi")
    async def cete_onayla_slash(self, ctx: commands.Context, cete_id: str):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        # ID veya isim ile cete bul
        gang = None
        try:
            gang = await db.get_gang_by_id(int(cete_id))
        except ValueError:
            gang = await db.get_gang_by_name(cete_id)

        if not gang:
            await self._send_error(ctx, f"Çete bulunamadi: {cete_id}")
            return

        if gang.get("approved"):
            await self._send_error(ctx, "Bu çete zaten onayli.")
            return

        await db.approve_gang(gang["id"])

        # FIX (v0.2.0): Sokak Ilk Yardimi perki olan cetelerin LIDERINE de
        # katilim hediyesi (1x Kirli Sargi) verilir. Eski kodda bu perk
        # hicbir yerde uygulanmiyordu.
        if any(
            p == 'sokak_ilk_yardim'
            for p in (gang.get('perks') or [])
        ):
            try:
                await db.add_item(gang["leader_id"], "Kirli Sargi", 1)
                await db.add_action_log(
                    "envanter", gang["leader_id"], None, "perk_kirli_sargi",
                    {"cete_id": gang["id"], "perk": "sokak_ilk_yardim",
                     "kime": "lider"},
                )
            except Exception as e:
                logger.error(f"Lidere Kirli Sargi verilemedi: {e}")

        # Lidere çete lideri rolunu ver
        leader = ctx.guild.get_member(gang["leader_id"])
        if leader:
            lider_rol_id = config.CETE_LIDER_ROLLERI.get(gang["type"])
            if lider_rol_id:
                lider_rol = ctx.guild.get_role(lider_rol_id)
                if lider_rol:
                    try:
                        await leader.add_roles(lider_rol, reason="Çete onaylandi")
                    except discord.Forbidden:
                        pass

        await db.add_action_log(
            "admin",
            ctx.author.id,
            gang["leader_id"],
            "cete_onayla",
            {"cete_id": gang["id"], "cete_adi": gang["name"]},
        )

        await self._admin_log(
            ctx.guild,
            "Çete Onaylama",
            ctx.author,
            leader,
            f"Çete: {gang['name']} ({gang['type']})",
        )

        # Çete onay log kanalina
        cete_log = (
            ctx.guild.get_channel(config.KANAL_CETE_ONAY_LOG) if ctx.guild else None
        )
        if cete_log:
            log_embed = discord.Embed(
                title="✅ Çete Onaylandi",
                description=(
                    f"**Çete Adi:** {gang['name']}\n"
                    f"**Tür:** {gang['type']}\n"
                    f"**Lider:** {leader.mention if leader else '?'}\n"
                    f"**Onaylayan:** {ctx.author.mention}"
                ),
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await cete_log.send(embed=log_embed)
            except Exception:
                pass

        # Liderin DM'ine bildiri
        if leader:
            try:
                dm_embed = embeds.success_embed(
                    "Çeteniz Onaylandi!",
                    f"**{gang['name']}** ({gang['type']}) cetesi onaylandi!\n"
                    f"Lider rolunuz verildi.\n"
                    f"Artik `/cete-davet` ile üye davet edebilirsiniz.",
                )
                await leader.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Çete Onaylandi", MSG_ADMIN_CETE_ONAYLA.format(isim=gang["name"])
            )
        )

    # ==================================================================
    # /cete-reddet
    # ==================================================================
    @commands.hybrid_command(
        name="cete-reddet",
        description="[Admin] Beklemedeki çete kurulum talebini reddeder",
    )
    @app_commands.describe(cete_id="Çete ID veya adi", sebep="Red sebebi")
    async def cete_reddet_slash(self, ctx: commands.Context, cete_id: str, sebep: str):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        gang = None
        try:
            gang = await db.get_gang_by_id(int(cete_id))
        except ValueError:
            gang = await db.get_gang_by_name(cete_id)

        if not gang:
            await self._send_error(ctx, f"Çete bulunamadi: {cete_id}")
            return

        if gang.get("approved"):
            await self._send_error(
                ctx, "Onayli çete reddedilemez. `/cete-feshet` kullanin."
            )
            return

        cete_adi = gang["name"]
        lider_id = gang["leader_id"]

        await db.reject_gang(gang["id"])

        await db.add_action_log(
            "admin",
            ctx.author.id,
            lider_id,
            "cete_reddet",
            {"cete_adi": cete_adi, "sebep": sebep},
        )

        await self._admin_log(
            ctx.guild,
            "Çete Reddetme",
            ctx.author,
            None,
            f"Çete: {cete_adi}\nSebep: {sebep}",
        )

        # Çete onay log kanalina
        cete_log = (
            ctx.guild.get_channel(config.KANAL_CETE_ONAY_LOG) if ctx.guild else None
        )
        if cete_log:
            log_embed = discord.Embed(
                title="❌ Çete Reddedildi",
                description=(
                    f"**Çete Adi:** {cete_adi}\n"
                    f"**Reddeden:** {ctx.author.mention}\n"
                    f"**Sebep:** {sebep}"
                ),
                color=config.RENK_HATA,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await cete_log.send(embed=log_embed)
            except Exception:
                pass

        # Liderin DM'ine bildiri
        leader = ctx.guild.get_member(lider_id)
        if leader:
            try:
                dm_embed = embeds.error_embed(
                    "Çete Talebi Reddedildi",
                    f"**{cete_adi}** adli çete kurulum talebiniz reddedildi.\n"
                    f"**Sebep:** {sebep}",
                )
                await leader.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Çete Reddedildi", MSG_ADMIN_CETE_RED.format(isim=cete_adi)
            )
        )

    # ==================================================================
    # /cete-feshet
    # ==================================================================
    @commands.hybrid_command(
        name="cete-feshet", description="[Admin] Onayli bir çeteyi zorla dagitir"
    )
    @app_commands.describe(cete_id="Çete ID veya adi", sebep="Fesih sebebi")
    async def cete_feshet_slash(
        self, ctx: commands.Context, cete_id: str, sebep: str = "Sebep belirtilmedi"
    ):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        gang = None
        try:
            gang = await db.get_gang_by_id(int(cete_id))
        except ValueError:
            gang = await db.get_gang_by_name(cete_id)

        if not gang:
            await self._send_error(ctx, f"Çete bulunamadi: {cete_id}")
            return

        cete_adi = gang["name"]
        cete_turu = gang["type"]
        lider_id = gang["leader_id"]

        # Üyelerin rollerini al
        members = await db.get_gang_members(gang["id"])
        uye_rol_id = config.CETE_UYE_ROLLERI.get(cete_turu)
        lider_rol_id = config.CETE_LIDER_ROLLERI.get(cete_turu)

        for member_data in members:
            m = ctx.guild.get_member(member_data["user_id"])
            if m:
                roller_kaldir = []
                if uye_rol_id:
                    r = ctx.guild.get_role(uye_rol_id)
                    if r and r in m.roles:
                        roller_kaldir.append(r)
                if lider_rol_id and member_data["role"] == "lider":
                    r = ctx.guild.get_role(lider_rol_id)
                    if r and r in m.roles:
                        roller_kaldir.append(r)
                if roller_kaldir:
                    try:
                        await m.remove_roles(*roller_kaldir, reason="Çete feshedildi")
                    except discord.Forbidden:
                        pass

        # Çeteyi sil
        await db.disband_gang(gang["id"])

        await db.add_action_log(
            "admin",
            ctx.author.id,
            lider_id,
            "cete_feshet",
            {"cete_adi": cete_adi, "sebep": sebep},
        )

        await self._admin_log(
            ctx.guild,
            "Çete Fesih",
            ctx.author,
            None,
            f"Çete: {cete_adi}\nSebep: {sebep}",
        )

        # Çete onay log kanalina
        cete_log = (
            ctx.guild.get_channel(config.KANAL_CETE_ONAY_LOG) if ctx.guild else None
        )
        if cete_log:
            log_embed = discord.Embed(
                title="⚠️ Çete Feshedildi",
                description=(
                    f"**Çete Adi:** {cete_adi}\n"
                    f"**Fesheden:** {ctx.author.mention}\n"
                    f"**Sebep:** {sebep}\n"
                    f"**Eski Üye Sayisi:** {len(members)}"
                ),
                color=config.RENK_HATA,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await cete_log.send(embed=log_embed)
            except Exception:
                pass

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Çete Feshedildi", MSG_ADMIN_CETE_FESHET.format(isim=cete_adi)
            )
        )

    # ==================================================================
    # /hava-durumu-degistir
    # ==================================================================
    @commands.hybrid_command(
        name="hava-durumu-degistir",
        description="[RP Yetkilisi/Admin] Sunucu genelindeki hava durumunu degistirir",
    )
    @app_commands.describe(durum="Yeni hava durumu")
    @app_commands.choices(
        durum=[
            app_commands.Choice(name="☀️ Gunesli", value="gunesli"),
            app_commands.Choice(name="🌫️ Yogun Sis", value="sisli"),
            app_commands.Choice(name="🌧️ Siddetli Yagmur", value="yagmurlu"),
            app_commands.Choice(name="🔥 Asiri Sicak", value="asiri_sicak"),
        ]
    )
    async def hava_durumu_degistir_slash(
        self, ctx: commands.Context, durum: app_commands.Choice[str]
    ):
        if not is_rp_yetkili(ctx.author):
            await self._send_error(
                ctx, "🚫 Bu komutu sadece RP Yetkilisi ve Admin kullanabilir."
            )
            return

        durum_kodu = durum.value
        hava_bilgi = HAVA_DURUMLARI.get(durum_kodu, {})

        await db.set_weather(durum_kodu, hava_bilgi.get("etkiler", {}))

        # Hava durumu kanalina duyuru
        hava_kanal = (
            ctx.guild.get_channel(config.KANAL_HAVA_DURUMU) if ctx.guild else None
        )
        if hava_kanal:
            embed = discord.Embed(
                title=f"{hava_bilgi.get('emoji', '🌦️')} Hava Durumu: {hava_bilgi.get('isim', '?')}",
                description=hava_bilgi.get("aciklama", ""),
                color=config.RENK_BILGI,
            )
            embed.set_footer(text=f"Degistiren: {ctx.author.display_name}")
            try:
                await hava_kanal.send(embed=embed)
            except Exception as e:
                logger.error(f"hava-durumu gonderilemedi: {e}")

        await db.add_action_log(
            "admin", ctx.author.id, None, "hava_durumu_degistir", {"durum": durum_kodu}
        )

        await self._admin_log(
            ctx.guild,
            "Hava Durumu Degistirme",
            ctx.author,
            None,
            f"Yeni durum: {hava_bilgi.get('isim', durum_kodu)}",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Hava Durumu Degistirildi",
                f"Yeni hava durumu: **{hava_bilgi.get('isim', '?')}**\n"
                f"{hava_bilgi.get('aciklama', '')}",
            )
        )

    # ==================================================================
    # /admin-canlandir (ölen karakteri geri getir)
    # ==================================================================
    @commands.hybrid_command(
        name="admin-canlandir",
        description="[Admin] Olu karakteri geri getirir (itiraz sonrasi)",
    )
    @app_commands.describe(hedef="Canlandirilacak kullanici")
    async def admin_canlandir_slash(self, ctx: commands.Context, hedef: discord.Member):
        if not is_admin(ctx.author):
            await self._send_error(ctx, "🚫 Bu komutu sadece Admin kullanabilir.")
            return

        user_data = await db.get_user(hedef.id)
        if not user_data:
            await self._send_error(ctx, "Hedef kullanici kayitli degil.")
            return

        if not user_data.get("is_dead"):
            await self._send_error(ctx, "Bu karakter zaten yasiyor.")
            return

        success = await db.revive_character(hedef.id)
        if not success:
            await self._send_error(
                ctx, "Karakter geri getirilemedi. Tombstone kaydi bulunamadi."
            )
            return

        await db.add_action_log("admin", ctx.author.id, hedef.id, "canlandir", {})

        await self._admin_log(
            ctx.guild,
            "Karakter Canlandirma",
            ctx.author,
            hedef,
            "Olu karakter geri getirildi (can=%50, acluk=%50)",
        )

        await self._send(ctx, 
            embed=embeds.success_embed(
                "Karakter Canlandirildi",
                f"{hedef.mention} karakteri geri getirildi!\n"
                f"Can, acluk ve susuzluk %50 olarak ayarlandi.",
            )
        )

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
    await bot.add_cog(AdminCog(bot))
    logger.info("AdminCog yuklendi")
