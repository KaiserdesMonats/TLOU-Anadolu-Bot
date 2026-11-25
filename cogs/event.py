"""
cogs/event.py - Event ve Dunya Dinamikleri
Komutlar: /event-bilgi, /event-kargo, /event-suru, /event-tuccar,
          /event-radyo, /event-aktifler
Eventler: kargo, suru, tuccar, radyo-sinyali
Admin/Yetkili tetikler, bot cooldown kontrol eder.
"""
import logging
import time
import random
import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db
from utils import embeds
from utils.constants import EVENT_KARGO_ICERIK, ITEMS
from utils.formatting import format_sure, format_tarih
from utils.localization import (
    MSG_EVENT_KARGO, MSG_EVENT_SURU, MSG_EVENT_TUCCAR, MSG_EVENT_RADYO,
    MSG_EVENT_COOLDOWN, MSG_KULLANICI_YOK, MSG_GOZLEMCİ_YETKISIZ,
)


logger = logging.getLogger("tlo.cogs.event")


# ==================================================================
# EVENT TURLERI
# ==================================================================
EVENT_TURLERI = {
    "kargo": {
        "isim": "Kargo Düsmesi",
        "emoji": "🪂",
        "cooldown_gun": config.EVENT_CD_GUN,
        "min_sure": 3600,  # 1 saat aktif kalir
        "max_sure": 7200,
    },
    "suru": {
        "isim": "Enfekte Sürüsü Göçü",
        "emoji": "🧟",
        "cooldown_gun": config.EVENT_CD_GUN,
        "min_sure": 1800,  # 30 dk
        "max_sure": 5400,  # 1.5 saat
    },
    "tuccar": {
        "isim": "Gezici Tüccar",
        "emoji": "🛒",
        "cooldown_gun": config.EVENT_CD_GUN,
        "min_sure": 7200,  # 2 saat aktif kalir
        "max_sure": 14400,  # 4 saat
    },
    "radyo": {
        "isim": "Gizemli Radyo Sinyali",
        "emoji": "📻",
        "cooldown_gun": 1,  # radyo daha sik
        "min_sure": 3600,
        "max_sure": 7200,
    },
}


# ==================================================================
# TÜCCAR ENVANTERI (rastgele 5-8 nadir esya)
# ==================================================================
def rastgele_tuccar_envanteri() -> list:
    """Tuccar icin rastgele nadir esya listesi olustur."""
    # Nadir/esya listesi (fiyat 2-3 kat)
    nadir_esyalar = [
        ("Konserve Et", 90),     # normal 30
        ("Kurutulmus Et", 120),  # normal 40
        ("Pismaniye", 150),      # normal 50
        ("Temizlenmis Su", 90),  # normal 30
        ("Cay", 105),            # normal 35
        ("Antibiyotik", 600),   # normal 200
        ("Agri Kesici", 240),    # normal 80
        ("Vitamin", 180),        # normal 60
        ("Bicak Sapi", 90),      # normal 30
        ("Namlu", 300),           # normal 100
        ("Tetik Mekanizması", 240),  # normal 80
        ("Sarjor", 180),          # normal 60
        ("Av Bıçağı", 360),      # normal 120
        ("9mm Mermi", 45),       # normal 15
        ("Tüfek Mermisi", 90),   # normal 30
        ("Ellenmis Cikmak", 210),  # normal 70
    ]
    # 5-8 rastgele sec
    adet = random.randint(5, 8)
    secim = random.sample(nadir_esyalar, min(adet, len(nadir_esyalar)))
    return [{"item": i[0], "fiyat": i[1]} for i in secim]


# ==================================================================
# TÜCCAR SATIN AL VIEW
# ==================================================================
class TuccarView(discord.ui.View):
    """Tuccardan satin alma view'i."""
    def __init__(self, member: discord.Member, envanter: list, event_id: int):
        super().__init__(timeout=600)
        self.member = member
        self.envanter = envanter
        self.event_id = event_id

        # Her esya icin bir buton (max 8 buton)
        for i, esya in enumerate(envanter[:8]):
            btn = discord.ui.Button(
                label=f"{esya['item']} - {esya['fiyat']} 🪙",
                style=discord.ButtonStyle.primary,
                custom_id=f"tuccar_{i}",
                row=i // 2  # 2 buton per satir
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.member.id:
                await interaction.response.send_message(
                    embed=embeds.error_embed("Hata",
                        "Bu tuccar senin icin degil."),
                    ephemeral=True
                )
                return

            esya = self.envanter[idx]
            user_data = await db.get_user(self.member.id)
            if not user_data:
                return

            if user_data['para'] < esya['fiyat']:
                await interaction.response.send_message(
                    embed=embeds.error_embed(
                        "Yetersiz Para",
                        f"**{esya['item']}** icin {esya['fiyat']} 🪙 gerekir. "
                        f"Sendeki: {user_data['para']} 🪙"
                    ),
                    ephemeral=True
                )
                return

            # Slot kontrolu
            slot_kapasite = await db.get_slot_capacity(self.member.id)
            envanter_adet = await db.get_inventory_count(self.member.id)
            if envanter_adet >= slot_kapasite:
                # Esya zaten var mi?
                esya_var = await db.has_item(self.member.id, esya['item'], 1)
                if not esya_var:
                    await interaction.response.send_message(
                        embed=embeds.error_embed(
                            "Envanter Dolu",
                            "Bu esyayi almak icin envanterinde yer yok."
                        ),
                        ephemeral=True
                    )
                    return

            # Alisveris
            await db.update_money(self.member.id, -esya['fiyat'])
            await db.add_item(self.member.id, esya['item'], 1)

            # Log
            await db.add_action_log('envanter', self.member.id, None,
                                     'tuccar_alim',
                                     {'esya': esya['item'],
                                      'fiyat': esya['fiyat']})

            await interaction.response.send_message(
                embed=embeds.success_embed(
                    "Satin Alindi",
                    f"**{esya['item']}** satin alindi!\n"
                    f"Odeme: {esya['fiyat']} 🪙\n"
                    f"Kalan bakiye: {user_data['para'] - esya['fiyat']} 🪙"
                ),
                ephemeral=True
            )

        return callback


# ==================================================================
# KARGO AÇMA VIEW
# ==================================================================
class KargoView(discord.ui.View):
    """Kargo kutusunu acma view."""
    def __init__(self, member: discord.Member, channel: discord.TextChannel):
        super().__init__(timeout=1800)  # 30 dk
        self.member = member
        self.channel = channel
        self.acildi = False

    @discord.ui.button(label="Kutuyu Aç", emoji="📦",
                       style=discord.ButtonStyle.primary)
    async def ac_btn(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        if self.acildi:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Bu kargo kutusu zaten acildi!"),
                ephemeral=True
            )
            return

        # Ilk ulasan kisi alir (herkes deneyebilir ama sadece ilk tiklayan alir)
        user_data = await db.get_user(interaction.user.id)
        if not user_data or user_data.get('gozlemci', 0):
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata",
                    "Sadece RP oyunculari kargo kutusu acabilir."),
                ephemeral=True
            )
            return

        if user_data.get('is_dead', 0):
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata",
                    "💀 Karakterin olu. Kargo kutusu acamazsin."),
                ephemeral=True
            )
            return

        self.acildi = True
        # Butonlari devre disi birak
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)

        # Icerigi dagit
        kazanclar = []
        for item in EVENT_KARGO_ICERIK:
            await db.add_item(interaction.user.id, item['item'], item['miktar'])
            kazanclar.append(f"• {item['item']} x{item['miktar']}")

        # Log
        await db.add_action_log('envanter', interaction.user.id, None,
                                 'kargo_acti',
                                 {'icerik': EVENT_KARGO_ICERIK})

        embed = embeds.success_embed(
            "📦 Kargo Kutusu Açildi!",
            f"**{interaction.user.mention}** kargo kutusunu acti!\n\n"
            f"**Icerik:**\n" + "\n".join(kazanclar)
        )
        embed.set_footer(text="Bu kargo kutusu artik bos.")
        await interaction.followup.send(embed=embed)

        # Eventi tamamla
        # (active_events tablosunda completed=1 yapilacak, ctx uzerinden)
        # Bu kisim event_id'ye gore yapilmali ama view'dan context zor olur.
        # Bu yuzden sadece log atildi, completed durumu tasks.py tarafindan halledilir.


# ==================================================================
# COG SINIFI
# ==================================================================
class EventBaseCog(commands.Cog):
    """Event ve dunya dinamikleri cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==================================================================
    # /event-bilgi
    # ==================================================================
    @commands.hybrid_command(
        name="event-bilgi",
        description="Event sistemini ve turlerini gosterir"
    )
    async def event_bilgi_slash(self, ctx: commands.Context):
        """Event tur listesi."""
        embed = discord.Embed(
            title="📡 Event Sistemi",
            description=(
                "TLOU Anadolu dunyasinda 4 cesit event bulunur.\n"
                "Eventler admin veya yetkili tarafindan tetiklenir.\n"
                "Ayni tur event 3-4 gun icinde tekrar edilmez."
            ),
            color=config.RENK_BILGI
        )

        for tur_id, tur in EVENT_TURLERI.items():
            embed.add_field(
                name=f"{tur['emoji']} {tur['isim']}",
                value=(
                    f"**Komut:** `/event-baslat {tur_id} <kanal>`\n"
                    f"**Cooldown:** {tur['cooldown_gun']} gun\n"
                    f"**Aktiflik Suresi:** {format_sure(tur['min_sure'])} - "
                    f"{format_sure(tur['max_sure'])}"
                ),
                inline=False
            )

        embed.set_footer(text="Otomatik eventler tasks.py tarafindan yonetilir.")
        await self._send(ctx, embed=embed)

    # ==================================================================
    # ORTAK EVENT BASLATMA FONKSIYONU
    # ==================================================================
    async def _event_baslat(self, ctx: commands.Context, event_turu: str,
                              kanal: discord.TextChannel, sure: int = None):
        """Ortak event baslatma fonksiyonu."""
        # Event turu gecerli mi?
        if event_turu not in EVENT_TURLERI:
            await self._send_error(ctx,
                f"Gecersiz event turu: {event_turu}\n"
                f"Gecerli turler: kargo, suru, tuccar, radyo"
            )
            return False

        tur_bilgi = EVENT_TURLERI[event_turu]

        # Cooldown kontrol
        last_time = await db.get_last_event_time(event_turu)
        if last_time:
            gecen = int(time.time()) - last_time
            cd_sure = tur_bilgi['cooldown_gun'] * 24 * 3600
            if gecen < cd_sure:
                kalan = cd_sure - gecen
                await self._send_error(ctx,
                    MSG_EVENT_COOLDOWN.format(
                        kalan_gun=kalan // 86400
                    )
                )
                return False

        # Sure belirle
        if sure is None:
            sure = random.randint(tur_bilgi['min_sure'], tur_bilgi['max_sure'])

        # RP lokasyon kontrol
        if kanal.category_id and kanal.category_id not in config.RP_KATEGORILERI:
            await self._send_error(ctx,
                "Event sadece RP lokasyon kanallarinda baslatilabilir."
            )
            return False

        # Event olustur
        event_id = await db.create_active_event(
            event_type=event_turu,
            channel_id=kanal.id,
            duration=sure,
            data={'baslatan': ctx.author.id}
        )

        # Event log
        await db.add_event_log(event_turu, {
            'baslatan': ctx.author.id,
            'kanal': kanal.id,
            'sure': sure,
            'event_id': event_id
        }, kanal.id)

        # Event log kanalina bildiri
        log_kanal = ctx.guild.get_channel(config.KANAL_EVENT_LOG) if ctx.guild else None
        if log_kanal:
            log_embed = discord.Embed(
                title=f"{tur_bilgi['emoji']} Event Baslatildi",
                description=(
                    f"**Tür:** {tur_bilgi['isim']}\n"
                    f"**Baslatan:** {ctx.author.mention}\n"
                    f"**Bölge:** {kanal.mention}\n"
                    f"**Süre:** {format_sure(sure)}\n"
                    f"**Event ID:** {event_id}"
                ),
                color=config.RENK_BILGI,
                timestamp=discord.utils.utcnow()
            )
            try:
                await log_kanal.send(embed=log_embed)
            except Exception as e:
                logger.error(f"event-log gonderilemedi: {e}")

        # Event duyurusu
        await self._event_duyuru(ctx, event_turu, kanal, sure, event_id)
        return True

    async def _event_duyuru(self, ctx: commands.Context, event_turu: str,
                             kanal: discord.TextChannel, sure: int, event_id: int):
        """Event'e gore duyuru mesaji gonder."""
        tur_bilgi = EVENT_TURLERI[event_turu]
        bolge_ad = kanal.mention

        if event_turu == "kargo":
            embed = discord.Embed(
                title="🪂 KARGO DÜŞMESİ!",
                description=MSG_EVENT_KARGO.format(bolge=bolge_ad),
                color=config.RENK_UYARI
            )
            embed.add_field(
                name="📦 İçerik (Tahmini)",
                value=(
                    "• Antibiyotik\n"
                    "• 9mm Mermi\n"
                    "• Temiz Su\n"
                    "• Temiz Sargı\n"
                    "• Vitamin"
                ),
                inline=False
            )
            # Kargo view gonder
            view = KargoView(ctx.author, kanal)
            embed.set_footer(
                text=f"Event ID: {event_id} | Süre: {format_sure(sure)}"
            )
            await kanal.send(content="@everyone", embed=embed, view=view,
                            allowed_mentions=discord.AllowedMentions.all())

        elif event_turu == "suru":
            embed = discord.Embed(
                title="⚠️ ENFEKTE SÜRÜSÜ GÖÇÜ!",
                description=MSG_EVENT_SURU.format(bolge=bolge_ad),
                color=config.RENK_HATA
            )
            embed.add_field(
                name="⚙️ Yapılması Gerekenler",
                value=(
                    "• `/gizlen` - Sessizce saklan\n"
                    "• Kanaldan uzaklaş - Bölgeyi terk et\n"
                    "\nBaşarısız olanlar: Yaralanma + Enfeksiyon Riski"
                ),
                inline=False
            )
            # Kanal topic guncelle
            try:
                await kanal.edit(topic="🧟 ENFEKTE SÜRÜSÜ - TEHLİKELİ!")
            except discord.Forbidden:
                pass
            embed.set_footer(
                text=f"Event ID: {event_id} | Süre: {format_sure(sure)}"
            )
            await kanal.send(content="@everyone", embed=embed,
                            allowed_mentions=discord.AllowedMentions.all())

        elif event_turu == "tuccar":
            # Rastgele envanter olustur
            tuccar_envanter = rastgele_tuccar_envanteri()
            # Envanteri DB'ye kaydet (data JSON olarak)
            # active_events tablosundaki data alanini guncelle
            await db._update_event_data(event_id, {'envanter': tuccar_envanter}) if hasattr(db, '_update_event_data') else None

            embed = discord.Embed(
                title="🛒 GEZİCİ TÜCCAR BELİRDİ!",
                description=MSG_EVENT_TUCCAR.format(bolge=bolge_ad),
                color=config.RENK_BASARI
            )

            # Envanteri listele
            env_metin = "\n".join(
                f"• {e['item']} - **{e['fiyat']} 🪙**"
                for e in tuccar_envanter
            )
            embed.add_field(
                name="📦 Satılık Eşyalar",
                value=env_metin,
                inline=False
            )
            embed.add_field(
                name="⚠️ Bilgi",
                value=(
                    "Fiyatlar piyasanın 2-3 katı!\n"
                    "Aşağıdaki butonlardan satın al"
                ),
                inline=False
            )

            # Ilk ulasabilen herkes alisveris yapsin diye ayri view'lar
            # Her kullanici kendi view'ini alacak (interaktif)
            # Pratik cozum: her butona tiklayinca satin alma yap
            await self._tuccar_buton_gonder(kanal, tuccar_envanter, event_id, sure)

            return  # diger flow'lar icin return

        elif event_turu == "radyo":
            # Rastgele bolge sec (sinyalin geldigi yer)
            bolgeler = list(config.KATEGORI_SEHIRLER.keys())
            kaynak_bolge = random.choice(bolgeler)

            embed = discord.Embed(
                title="📻 GİZEMLİ RADYO SİNYALİ",
                description=MSG_EVENT_RADYO.format(bolge=kaynak_bolge),
                color=config.RENK_BILGI
            )
            embed.add_field(
                name="🔍 Nasıl Takip Edilir?",
                value=(
                    f"Bu sinyal **{kaynak_bolge}** bölgesinden geliyor.\n"
                    f"Oraya gidip `/arastir` yapabilirsiniz.\n"
                    f"Gerçek ganimet mi, yoksa tuzak mı? Sadece gidip görebilirsiniz."
                ),
                inline=False
            )
            embed.set_footer(
                text=f"Event ID: {event_id} | Süre: {format_sure(sure)}"
            )

            # Genel telsiz agina gonder
            telsiz_kanal = ctx.guild.get_channel(config.KANAL_GENEL_TELSIZ_AGI) if ctx.guild else None
            if telsiz_kanal:
                try:
                    await telsiz_kanal.send(embed=embed)
                except Exception as e:
                    logger.error(f"genel-telsiz gonderilemedi: {e}")
            else:
                await kanal.send(embed=embed)

    async def _tuccar_buton_gonder(self, kanal: discord.TextChannel,
                                     envanter: list, event_id: int, sure: int):
        """Tuccar icin satin alma menusu gonder.
        Her kullanici kendi menusu acilir.
        """
        # Tum server'a acik bir ana mesaj gonder
        # Altina interaktif butonlar ekle
        # Pratik cozum: her kullanici kendi ephemeral menusu acar
        # Discord JS view ile yapilabilir
        embed = discord.Embed(
            title="🛒 Gezici Tüccar",
            description=(
                f"Tüccar **{kanal.mention}** bölgesinde belirdi!\n\n"
                f"Satılık eşyaları görmek için aşağıdaki butona tıkla."
            ),
            color=config.RENK_BASARI
        )

        # Tek bir "Envanteri Gör" butonu
        view = TuccarGirisView(envanter, event_id, sure)
        embed.set_footer(
            text=f"Event ID: {event_id} | Kalan süre: {format_sure(sure)}"
        )
        await kanal.send(embed=embed, view=view)


class TuccarGirisView(discord.ui.View):
    """Tuccara ulasmak icin ana buton view."""
    def __init__(self, envanter: list, event_id: int, sure: int):
        super().__init__(timeout=sure)
        self.envanter = envanter
        self.event_id = event_id
        self.sure = sure

    @discord.ui.button(label="Tüccara Git", emoji="🛒",
                       style=discord.ButtonStyle.primary)
    async def giris_btn(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        user_data = await db.get_user(interaction.user.id)
        if not user_data:
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", "Kayitli degilsin."),
                ephemeral=True
            )
            return

        if user_data.get('gozlemci', 0):
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata", MSG_GOZLEMCİ_YETKISIZ),
                ephemeral=True
            )
            return

        if user_data.get('is_dead', 0):
            await interaction.response.send_message(
                embed=embeds.error_embed("Hata",
                    "💀 Karakterin olu. Tuccar ile etkilesim kuramazsin."),
                ephemeral=True
            )
            return

        # Tuccar menusu (ephemeral)
        view = TuccarView(interaction.user, self.envanter, self.event_id)
        env_metin = "\n".join(
            f"• {e['item']} - **{e['fiyat']} 🪙**"
            for e in self.envanter
        )
        embed = discord.Embed(
            title="🛒 Tüccarın Tezgahı",
            description=f"**Bakiyen:** {user_data['para']} 🪙\n\n**Satılık Eşyalar:**\n{env_metin}",
            color=config.RENK_BASARI
        )
        embed.set_footer(text="30 dakika içinde alışveriş yapmalısın.")
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )


# ==================================================================
# COG SINIFI DEVAM
# ==================================================================
class EventCog(EventBaseCog):
    """Event cog (devam)."""

    # ==================================================================
    # /event-baslat (admin yetkili)
    # ==================================================================
    @commands.hybrid_command(
        name="event-baslat",
        description="[RP Yetkilisi] Bir event baslatir"
    )
    @app_commands.describe(
        tur="Event turu",
        kanal="Event baslatilacak kanal"
    )
    @app_commands.choices(tur=[
        app_commands.Choice(name="🪂 Kargo Düşmesi", value="kargo"),
        app_commands.Choice(name="🧟 Enfekte Sürüsü", value="suru"),
        app_commands.Choice(name="🛒 Gezici Tüccar", value="tuccar"),
        app_commands.Choice(name="📻 Radyo Sinyali", value="radyo"),
    ])
    async def event_baslat_slash(self, ctx: commands.Context,
                                   tur: app_commands.Choice[str],
                                   kanal: discord.TextChannel):
        """Event baslatir."""
        from utils.checks import is_rp_yetkili
        if not is_rp_yetkili(ctx.author):
            await self._send_error(ctx,
                "🚫 Bu komutu sadece RP Yetkilisi ve Admin kullanabilir."
            )
            return

        # Hybrid komutlarda slash cagrisi Choice, prefix cagrisi ise duz
        # metin gonderir. Her iki bicimi de destekle.
        event_turu = tur.value if isinstance(tur, app_commands.Choice) else tur
        await self._event_baslat(ctx, event_turu, kanal)

    # ==================================================================
    # /event-aktifler
    # ==================================================================
    @commands.hybrid_command(
        name="event-aktifler",
        description="Su an aktif olan eventleri listeler"
    )
    async def event_aktifler_slash(self, ctx: commands.Context):
        """Aktif eventleri listeler."""
        events = await db.get_active_events()

        if not events:
            await self._send(ctx, embed=embeds.info_embed(
                "Aktif Event",
                "Su an aktif event yok."
            ))
            return

        embed = discord.Embed(
            title="📡 Aktif Eventler",
            description=f"Toplam **{len(events)}** aktif event var.",
            color=config.RENK_BILGI
        )

        for e in events:
            tur = e.get('event_type', '?')
            tur_bilgi = EVENT_TURLERI.get(tur, {})
            kanal = self.bot.get_channel(e.get('channel_id'))
            kanal_ad = kanal.mention if kanal else "Bilinmiyor"

            now = int(time.time())
            kalan = e.get('end_time', 0) - now
            kalan_str = format_sure(kalan) if kalan > 0 else "Sona erdi"

            embed.add_field(
                name=f"{tur_bilgi.get('emoji', '📡')} {tur_bilgi.get('isim', tur)}",
                value=(
                    f"**Bölge:** {kanal_ad}\n"
                    f"**Kalan Süre:** {kalan_str}\n"
                    f"**Event ID:** {e.get('id')}"
                ),
                inline=False
            )

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
    await bot.add_cog(EventCog(bot))
    logger.info("EventCog yuklendi")
