"""
cogs/kayit.py - Kayit Sistemi
Hybrid komut: /kayit ve tlo.kayit
Iki yol: Gozlemci veya RP Oyuncusu.
"""
import logging
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.checks import is_kayit_yetkili, is_kayitli
from utils.localization import (
    MSG_KAYIT_YETKISIZ, MSG_KAYIT_YANLIS_KANAL, MSG_KAYIT_BASLATILDI,
    MSG_GOZLEMCI_BASARILI, MSG_GOZLEMCI_ISIM_GEREKLI,
    MSG_RP_ADIM_SEHIR, MSG_RP_ADIM_MESLEK, MSG_RP_ADIM_BILGI,
    MSG_RP_YAS_HATA, MSG_RP_BASARILI,
)

logger = logging.getLogger("tlo.cogs.kayit")


# ==================================================================
# HELPER: Rol yonetimi
# ==================================================================
async def assign_gozlemci_roles(member: discord.Member, isim: str):
    """Gozlemci icin rolleri ayarla."""
    # Kayitsiz rolunu sil
    kayitsiz = member.guild.get_role(config.ROL_KAYITSIZ)
    if kayitsiz and kayitsiz in member.roles:
        await member.remove_roles(kayitsiz, reason="Gozlemci kaydi")
    # Uye rolunu ver
    uye = member.guild.get_role(config.ROL_UYE)
    if uye and uye not in member.roles:
        await member.add_roles(uye, reason="Gozlemci kaydi")
    # Nick degistir
    try:
        await member.edit(nick=isim, reason="Gozlemci kaydi")
    except discord.Forbidden:
        pass


async def assign_rp_roles(member: discord.Member, isim: str, soyisim: str,
                          sehir: str, meslek_rol_id: int):
    """RP oyuncusu icin rolleri ayarla."""
    # Kayitsiz rolunu sil
    kayitsiz = member.guild.get_role(config.ROL_KAYITSIZ)
    if kayitsiz and kayitsiz in member.roles:
        await member.remove_roles(kayitsiz, reason="RP kaydi")
    # Uye rolunu ver
    uye = member.guild.get_role(config.ROL_UYE)
    if uye and uye not in member.roles:
        await member.add_roles(uye, reason="RP kaydi")
    # Sehir rolunu ver
    sehir_rol_id = config.SEHIR_ROLLERI.get(sehir)
    if sehir_rol_id:
        sehir_rol = member.guild.get_role(sehir_rol_id)
        if sehir_rol and sehir_rol not in member.roles:
            await member.add_roles(sehir_rol, reason=f"Sehir: {sehir}")
    # Meslek rolunu ver
    meslek_rol = member.guild.get_role(meslek_rol_id)
    if meslek_rol and meslek_rol not in member.roles:
        await member.add_roles(meslek_rol, reason="RP meslek")
    # Nick degistir
    tam_isim = f"{isim} {soyisim}"
    try:
        await member.edit(nick=tam_isim[:32], reason="RP kaydi")
    except discord.Forbidden:
        pass


async def send_kayit_log(member: discord.Member, kayit_type: str, **kwargs):
    """kayıt-log kanalına mesaj gönder."""
    if not member.guild:
        return
    kanal = member.guild.get_channel(config.KANAL_KAYIT_LOG)
    if not kanal:
        logger.warning(f"kayıt-log kanalı bulunamadı (ID: {config.KANAL_KAYIT_LOG})")
        return
    try:
        if kayit_type == "gozlemci":
            embed = discord.Embed(
                title="👁️ Gözlemci Kaydı",
                description=f"{member.mention} gözlemci olarak kaydoldu.",
                color=config.RENK_BILGI,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="İsim", value=kwargs.get('isim', '?'))
        else:  # rp
            embed = discord.Embed(
                title="🎭 RP Oyuncusu Kaydı",
                description=f"{member.mention} RP oyuncusu olarak kaydoldu.",
                color=config.RENK_BASARI,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="İsim", value=f"{kwargs.get('isim', '?')} {kwargs.get('soyisim', '')}".strip())
            embed.add_field(name="Yaş", value=str(kwargs.get('yas', '?')))
            embed.add_field(name="Şehir", value=kwargs.get('sehir', '?'))
            embed.add_field(name="Meslek", value=kwargs.get('meslek', '?'))
        embed.set_footer(text=f"User ID: {member.id}")
        await kanal.send(embed=embed)
        logger.info(f"Kayıt logu gönderildi: {member.id} ({kayit_type})")
    except discord.Forbidden:
        logger.error(f"kayıt-log kanalına mesaj izni yok")
    except Exception as e:
        logger.error(f"kayıt-log gönderilemedi: {e}")


# ==================================================================
# MODAL'LAR
# ==================================================================
class GozlemciModal(discord.ui.Modal, title='Gözlemci Kaydı'):
    """Sadece isim sorulur."""
    isim = discord.ui.TextInput(
        label='İsminiz',
        placeholder='Örnek: Ahmet',
        required=True,
        min_length=2,
        max_length=30,
    )

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        isim = str(self.isim.value).strip()
        if not isim:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Lütfen bir isim girin."),
                ephemeral=True
            )
            return
        try:
            # Önce kullanıcıya cevap ver (modal kapanır)
            await interaction.response.send_message(
                embed=embeds.success_embed(
                    "Kayıt Tamamlandı",
                    f"Gözlemci olarak kaydedildin. İyi eğlenceler!"
                ),
                ephemeral=True
            )
            # Sonra işlemleri yap
            await assign_gozlemci_roles(self.member, isim)
            await db.complete_gozlemci_kayit(self.member.id, isim)
            await send_kayit_log(self.member, "gozlemci", isim=isim)
        except Exception as e:
            logger.error(f"Gözlemci kayıt hatası: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        embed=embeds.error_embed("Hata",
                            f"Kayıt sırasında bir hata oluştu: {e}"),
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        embed=embeds.error_embed("Hata", "Kayıt sırasında bir hata oluştu."),
                        ephemeral=True
                    )
            except Exception:
                pass


class RPModal(discord.ui.Modal, title='RP Oyuncusu Kaydı - Bilgiler'):
    """İsim, soyisim, yaş sorulur."""
    isim = discord.ui.TextInput(
        label='İsim',
        placeholder='Örnek: Mehmet',
        required=True,
        min_length=2,
        max_length=20,
    )
    soyisim = discord.ui.TextInput(
        label='Soyisim',
        placeholder='Örnek: Yılmaz',
        required=True,
        min_length=2,
        max_length=20,
    )
    yas = discord.ui.TextInput(
        label='Yaş (15-80)',
        placeholder='Örnek: 25',
        required=True,
        min_length=2,
        max_length=2,
    )

    def __init__(self, member: discord.Member, sehir: str,
                meslek_label: str, meslek_rol_id: int):
        super().__init__()
        self.member = member
        self.sehir = sehir
        self.meslek_label = meslek_label
        self.meslek_rol_id = meslek_rol_id

    async def on_submit(self, interaction: discord.Interaction):
        isim = str(self.isim.value).strip()
        soyisim = str(self.soyisim.value).strip()
        yas_str = str(self.yas.value).strip()

        # Yaş kontrolü
        try:
            yas = int(yas_str)
        except ValueError:
            await interaction.response.send_message(
                embed=embeds.error_embed("Yaş Hatası",
                    "Yaş 15-80 arasında olmalı ve sayı olmalı."),
                ephemeral=True
            )
            return
        if yas < config.MIN_YAS or yas > config.MAX_YAS:
            await interaction.response.send_message(
                embed=embeds.error_embed("Yaş Hatası",
                    f"Yaş {config.MIN_YAS}-{config.MAX_YAS} arasında olmalı."),
                ephemeral=True
            )
            return

        try:
            # Önce kullanıcıya cevap ver (modal kapanır)
            await interaction.response.send_message(
                embed=embeds.success_embed(
                    "Kayıt Tamamlandı",
                    f"RP Oyuncusu olarak kaydedildin! `/profil` komutunu kullanabilirsin."
                ),
                ephemeral=True
            )
            # Sonra işlemleri yap
            await assign_rp_roles(self.member, isim, soyisim,
                                   self.sehir, self.meslek_rol_id)
            await db.complete_rp_kayit(
                self.member.id, isim, soyisim, yas,
                self.sehir, self.meslek_label
            )
            await send_kayit_log(
                self.member, "rp",
                isim=isim, soyisim=soyisim, yas=yas,
                sehir=self.sehir, meslek=self.meslek_label
            )
        except Exception as e:
            logger.error(f"RP kayıt hatası: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        embed=embeds.error_embed("Hata",
                            f"Kayıt sırasında bir hata oluştu: {e}"),
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        embed=embeds.error_embed("Hata", "Kayıt sırasında bir hata oluştu."),
                        ephemeral=True
                    )
            except Exception:
                pass


# ==================================================================
# VIEWS (Buton + Dropdown)
# ==================================================================
class KayitView(discord.ui.View):
    """İlk menü: Gözlemci / RP Oyuncusu seçimi."""
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=300)
        self.target_member = target_member

    @discord.ui.button(label="Gözlemci Ol", emoji="👁️", style=discord.ButtonStyle.secondary)
    async def gozlemci_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin için değil."),
                ephemeral=True
            )
            return
        modal = GozlemciModal(self.target_member)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="RP Oyuncusu Ol", emoji="🎭", style=discord.ButtonStyle.primary)
    async def rp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin için değil."),
                ephemeral=True
            )
            return
        view = RPSecimView(self.target_member)
        await interaction.response.send_message(
            embed=embeds.info_embed("Adim 1: Sehir", MSG_RP_ADIM_SEHIR),
            view=view,
            ephemeral=True
        )


class SehirDropdown(discord.ui.Select):
    """Sehir secim dropdown'i."""
    def __init__(self, member: discord.Member):
        self.member = member
        options = []
        for sehir, _ in config.SEHIR_ROLLERI.items():
            options.append(discord.SelectOption(
                label=sehir,
                value=sehir,
                description=f"{sehir} sehrinde yasamak"
            ))
        super().__init__(
            placeholder='Sehrini sec...',
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu menü senin için değil."),
                ephemeral=True
            )
            return
        sehir = self.values[0]
        # Meslek view'una gec
        view = RPSecimView(self.member)
        view.sehir = sehir
        view.meslek_aktif = True
        view.meslek_dropdown.disabled = False
        await interaction.response.edit_message(
            embed=embeds.info_embed("Adim 2: Meslek", MSG_RP_ADIM_MESLEK),
            view=view
        )


class MeslekDropdown(discord.ui.Select):
    """Meslek grubu secim dropdown'i."""
    def __init__(self, member: discord.Member):
        self.member = member
        options = []
        for grup in config.MESLEK_GRUPLARI.keys():
            options.append(discord.SelectOption(
                label=grup,
                value=grup,
                description=f"{grup} meslek grubu"
            ))
        super().__init__(
            placeholder='Meslek grubunu sec...',
            min_values=1,
            max_values=1,
            options=options,
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu menü senin için değil."),
                ephemeral=True
            )
            return
        grup = self.values[0]
        # Detay dropdown'ina gec (meslek secimi)
        view = RPSecimView(self.member)
        view.sehir = self.view.sehir
        view.meslek_grup = grup
        view.meslek_aktif = True
        view.meslek_dropdown.disabled = False
        view.detay_aktif = True
        view.detay_dropdown = MeslekDetayDropdown(self.member, grup)
        view.detay_dropdown.disabled = False
        view.add_item(view.detay_dropdown)
        await interaction.response.edit_message(
            embed=embeds.info_embed("Adim 2b: Meslek Sec", f"**{grup}** grubundan bir meslek sec:"),
            view=view
        )


class MeslekDetayDropdown(discord.ui.Select):
    """Meslek detay secim dropdown'i (meslek grubu icindeki roller)."""
    def __init__(self, member: discord.Member, meslek_grup: str):
        self.member = member
        self.meslek_grup = meslek_grup
        roller = config.MESLEK_GRUPLARI.get(meslek_grup, [])
        options = []
        for label, _ in roller:
            options.append(discord.SelectOption(
                label=label,
                value=f"{label}",
                description=f"{label} rolunu al"
            ))
        super().__init__(
            placeholder=f'{meslek_grup} icin meslek sec...',
            min_values=1,
            max_values=1,
            options=options,
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu menü senin için değil."),
                ephemeral=True
            )
            return
        secim = self.values[0]
        # Meslek rol ID'sini bul
        roller = config.MESLEK_GRUPLARI.get(self.meslek_grup, [])
        meslek_rol_id = None
        for label, rol_id in roller:
            if label == secim:
                meslek_rol_id = rol_id
                break
        if not meslek_rol_id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Meslek bulunamadi."),
                ephemeral=True
            )
            return
        # Tamamla butonunu aktif et
        view = RPSecimView(self.member)
        view.sehir = self.view.sehir
        view.meslek_grup = self.meslek_grup
        view.meslek_label = secim
        view.meslek_rol_id = meslek_rol_id
        view.tamamla_aktif = True
        view.tamamla_btn.disabled = False
        await interaction.response.edit_message(
            embed=embeds.info_embed(
                "Son Adim: Bilgileri Gir",
                f"**Sehir:** {view.sehir}\n"
                f"**Meslek:** {secim}\n\n"
                f"{MSG_RP_ADIM_BILGI}"
            ),
            view=view
        )


class RPSecimView(discord.ui.View):
    """RP kayit icin cok adimli secim view'i."""
    def __init__(self, member: discord.Member):
        super().__init__(timeout=600)
        self.member = member
        self.sehir = None
        self.meslek_grup = None
        self.meslek_label = None
        self.meslek_rol_id = None
        self.meslek_aktif = False
        self.detay_aktif = False
        self.tamamla_aktif = False

        # Sehir dropdown (her zaman aktif)
        self.add_item(SehirDropdown(member))

        # Meslek dropdown (baslangicta disabled)
        self.meslek_dropdown = MeslekDropdown(member)
        self.add_item(self.meslek_dropdown)

        # Meslek detay dropdown (baslangicta disabled)
        self.detay_dropdown = None  # meslek grubu secilince olusturulur

        # Tamamla butonu (baslangicta disabled)
        self.tamamla_btn = discord.ui.Button(
            label="Bilgileri Gir ve Tamamla",
            emoji="✅",
            style=discord.ButtonStyle.success,
            disabled=True
        )
        self.tamamla_btn.callback = self.tamamla_callback
        self.add_item(self.tamamla_btn)

    async def tamamla_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu buton senin için değil."),
                ephemeral=True
            )
            return
        if not self.sehir or not self.meslek_rol_id or not self.meslek_label:
            await interaction.response.send_message(
                embed=embeds.error_embed("Eksik Bilgi",
                                          "Lutfen once sehir ve meslek secin."),
                ephemeral=True
            )
            return
        modal = RPModal(
            self.member,
            self.sehir,
            self.meslek_label,
            self.meslek_rol_id
        )
        await interaction.response.send_modal(modal)


# ==================================================================
# COG SINIFI
# ==================================================================
class KayitCog(commands.Cog):
    """Kayit sistemi cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="kayit",
        description="Kullanici kaydi yapar (kullanici verilmezse kendini kaydeder)"
    )
    @app_commands.describe(
        kullanici="Kayit edilecek kullanici (bos = kendini kaydet)"
    )
    async def kayit_slash(self, ctx: commands.Context,
                          kullanici: discord.Member = None):
        """Kayit komutu.
        - Yetkili (Kayit/RP/Admin) baskasini kayit edebilir: /kayit @kullanici
        - Normal uye kendini kayit edebilir: /kayit
        """
        # Hedef kullanici belirle
        if kullanici is None:
            # Self-kayit
            kullanici = ctx.author
            is_self = True
        else:
            is_self = (kullanici.id == ctx.author.id)

        # Baskasini kayit etmek icin yetki gerekli
        if not is_self:
            if not isinstance(ctx.author, discord.Member) or not is_kayit_yetkili(ctx.author):
                await self._send_msg(ctx,
                    embeds.error_embed("Yetkisiz",
                        "Baskasini kayit etmek icin yetkili olman gerekir. "
                        "Kendini kayit etmek icin: `/kayit` (parametresiz)"),
                    ephemeral=True
                )
                return

        # Kanal kontrolu
        if ctx.channel.id not in config.KAYIT_KANALLARI:
            await self._send_msg(ctx,
                embeds.error_embed("Yanlis Kanal", MSG_KAYIT_YANLIS_KANAL),
                ephemeral=True
            )
            return

        # Zaten kayitli mi?
        if is_kayitli(kullanici):
            await self._send_msg(ctx,
                embeds.warning_embed(
                    "Zaten Kayitli",
                    f"{kullanici.mention} zaten kayitli. "
                    f"Yeniden kayit icin once admin ile gorusun."
                ),
                ephemeral=True
            )
            return

        # Kayıt menüsünü göster
        view = KayitView(kullanici)
        embed = embeds.info_embed(
            "Kayıt Menüsü",
            f"{kullanici.mention}, aşağıdan bir seçenek seçin:\n\n"
            f"👁️ **Gözlemci Ol** - Sadece izlersin, RP'ye katılmazsın\n"
            f"🎭 **RP Oyuncusu Ol** - Karakter oluşturup RP'ye katılırsın"
        )
        await self._send_msg(ctx, content=kullanici.mention, embed=embed, view=view)

    async def _send_msg(self, ctx: commands.Context, embed=None, content=None,
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


# ==================================================================
# SETUP
# ==================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(KayitCog(bot))
    logger.info("KayitCog yuklendi")
