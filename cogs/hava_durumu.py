"""
cogs/hava_durumu.py - Hava Durumu Sistemi
Otomatik: Her gun saat 21:00'de rastgele hava durumu atar.
Manuel: /hava-durumu (gosterir), /hava-durumu-degistir admin cog'unda.
Gece bot mesaj atmaz kurali: 21:00 sonrasi otomatik mesaj sadece hava durumu icin istisna.
"""

import logging
import random
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from database import db
from utils import embeds
from utils.constants import HAVA_DURUMLARI
from utils.localization import (
    MSG_HAVA_GUNESLI,
    MSG_HAVA_SIS,
    MSG_HAVA_YAGMUR,
    MSG_HAVA_SICAK,
)


logger = logging.getLogger("tlo.cogs.hava_durumu")

TZ_ISTANBUL = timezone(timedelta(hours=3))

# Hava durumu olasiliklari (yuzdelik)
HAVA_OLASILIKLARI = {
    "gunesli": 0.50,  # %50 - en yaygin
    "sisli": 0.20,  # %20
    "yagmurlu": 0.20,  # %20
    "asiri_sicak": 0.10,  # %10
}


def rastgele_hava_durumu() -> str:
    """Agirlikli rastgele hava durumu sec."""
    r = random.random()
    toplam = 0
    for durum, olasilik in HAVA_OLASILIKLARI.items():
        toplam += olasilik
        if r < toplam:
            return durum
    return "gunesli"  # varsayilan


# ==================================================================
# COG SINIFI
# ==================================================================
class HavaDurumuCog(commands.Cog):
    """Hava durumu sistemi cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Gorevleri baslat
        self.hava_durumu_gorevi.start()
        # Event expire kontrol gorevi (her 30 dk)
        self.event_kontrol_gorevi.start()

    def cog_unload(self):
        """Cog kaldirilirken gorevleri durdur."""
        self.hava_durumu_gorevi.cancel()
        self.event_kontrol_gorevi.cancel()

    # ==================================================================
    # GUNLUK HAVA DURUMU GOREVI (her gun 21:00)
    # ==================================================================
    @tasks.loop(minutes=1)
    async def hava_durumu_gorevi(self):
        """Her dakika kontrol eder, 21:00'de hava durumu atar.
        Bu sekilde bot restart olsa bile saati kacirmaz.
        """
        now = datetime.now(TZ_ISTANBUL)

        # Sadece 21:00'da calisir
        if now.hour != config.HAVA_DURUMU_SAATI or now.minute != 0:
            return

        # Bugun hava durumu zaten atildi mi kontrol et
        bugun = now.date().isoformat()
        current_weather = await db.get_current_weather()
        if current_weather and current_weather.get("date", "").startswith(bugun):
            return  # bugun atildi

        # Yeni hava durumu olustur
        durum = rastgele_hava_durumu()
        hava_bilgi = HAVA_DURUMLARI.get(durum, {})

        await db.set_weather(durum, hava_bilgi.get("etkiler", {}))

        # Hava durumu kanalina duyuru
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        kanal = guild.get_channel(config.KANAL_HAVA_DURUMU)
        if not kanal:
            logger.warning("hava-durumu kanali bulunamadi")
            return

        # Embed olustur
        embed = discord.Embed(
            title=f"{hava_bilgi.get('emoji', '🌦️')} Gunluk Hava Durumu",
            description=(
                f"**Tarih:** {now.strftime('%d.%m.%Y')}\n"
                f"**Durum:** {hava_bilgi.get('isim', '?')}\n\n"
                f"{hava_bilgi.get('aciklama', '')}"
            ),
            color=config.RENK_BILGI,
        )

        # Etkileri detayli goster
        etkiler = hava_bilgi.get("etkiler", {})
        if etkiler:
            etki_listesi = []
            for key, val in etkiler.items():
                if isinstance(val, bool):
                    etki_listesi.append(f"• {key}: {'Aktif' if val else 'Devre disi'}")
                elif isinstance(val, (int, float)):
                    if val > 0:
                        etki_listesi.append(f"• {key}: +{int(val * 100)}%")
                    else:
                        etki_listesi.append(f"• {key}: {int(val * 100)}%")
            if etki_listesi:
                embed.add_field(
                    name="⚙️ Oyun Etkileri", value="\n".join(etki_listesi), inline=False
                )

        embed.set_footer(text=f"TLOU Anadolu • Gunluk Hava Raporu")

        try:
            await kanal.send(embed=embed)
            logger.info(f"Gunluk hava durumu atildi: {durum}")

            # Event-log kanalina da kayit
            event_log = guild.get_channel(config.KANAL_EVENT_LOG)
            if event_log:
                log_embed = discord.Embed(
                    title="🌦️ Gunluk Hava Durumu Atandi",
                    description=(
                        f"**Durum:** {hava_bilgi.get('isim', durum)}\n"
                        f"**Zaman:** {now.strftime('%H:%M')}"
                    ),
                    color=config.RENK_BILGI,
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await event_log.send(embed=log_embed)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Hava durumu gonderilemedi: {e}")

    @hava_durumu_gorevi.before_loop
    async def hava_durumu_before(self):
        """Bot hazir olana kadar bekle."""
        await self.bot.wait_until_ready()

    # ==================================================================
    # EVENT EXPIRE KONTROL GOREVI (her 30 dakika)
    # ==================================================================
    @tasks.loop(minutes=30)
    async def event_kontrol_gorevi(self):
        """Aktif eventlerin suresi dolmus mu kontrol et, tamamla."""
        try:
            active_events = await db.get_active_events()
            for event in active_events:
                now_ts = int(datetime.now(timezone.utc).timestamp())
                if event.get("end_time", 0) <= now_ts:
                    # Event suresi dolmus
                    await db.complete_active_event(event["id"])

                    # Event log
                    event_type = event.get("event_type", "bilinmeyen")
                    channel_id = event.get("channel_id")

                    guild = self.bot.get_guild(config.GUILD_ID)
                    if guild and channel_id:
                        kanal = guild.get_channel(channel_id)
                        if kanal:
                            # Event turune gore kapanis mesaji
                            kapanis_metni = self._kapanis_metni(event_type)
                            if kapanis_metni:
                                embed = embeds.info_embed(
                                    "⏰ Event Sona Erdi", kapanis_metni
                                )
                                try:
                                    await kanal.send(embed=embed)
                                except Exception:
                                    pass

                    logger.info(f"Event tamamlandi (suresi doldu): {event_type}")
        except Exception as e:
            logger.error(f"Event kontrol hatasi: {e}")

    @event_kontrol_gorevi.before_loop
    async def event_kontrol_before(self):
        await self.bot.wait_until_ready()

    def _kapanis_metni(self, event_type: str) -> str:
        """Event turune gore kapanis mesaji."""
        if event_type == "kargo":
            return "🪂 Kargo dusmesi eventi sona erdi. Bolgede artik kargo kutusu yok."
        elif event_type == "suru":
            return (
                "🧟 Enfekte surusu bolgeyi terk etti. Bolge tekrar guvenli (gorunuste)."
            )
        elif event_type == "tuccar":
            return "🛒 Gezici tüccar yola cikti. Baska zaman tekrar gelebilir."
        elif event_type == "radyo":
            return "📻 Radyo sinyali kayboldu. Telsizde sadece cizirti var."
        return f"Event ({event_type}) sona erdi."

    # ==================================================================
    # /hava-durumu (mevcut durumu gosterir)
    # ==================================================================
    @commands.hybrid_command(
        name="hava-durumu", description="Su anki hava durumunu gosterir"
    )
    async def hava_durumu_slash(self, ctx: commands.Context):
        """Mevcut hava durumunu gosterir."""
        current = await db.get_current_weather()
        if not current:
            await self._send(ctx, 
                embed=embeds.info_embed(
                    "Hava Durumu",
                    "Henuz hava durumu kaydi yok. Ilk gunluk hava durumu 21:00'de atilir.",
                )
            )
            return

        durum = current.get("condition", "gunesli")
        hava_bilgi = HAVA_DURUMLARI.get(durum, {})

        embed = discord.Embed(
            title=f"{hava_bilgi.get('emoji', '🌦️')} Hava Durumu",
            description=(
                f"**Durum:** {hava_bilgi.get('isim', durum)}\n\n"
                f"{hava_bilgi.get('aciklama', '')}"
            ),
            color=config.RENK_BILGI,
        )

        # Etkiler
        etkiler = hava_bilgi.get("etkiler", {})
        if etkiler:
            etki_listesi = []
            for key, val in etkiler.items():
                if isinstance(val, bool):
                    etki_listesi.append(f"• {key}: {'Aktif' if val else 'Devre disi'}")
                elif isinstance(val, (int, float)):
                    isaret = "+" if val > 0 else ""
                    etki_listesi.append(f"• {key}: {isaret}{int(val * 100)}%")
            if etki_listesi:
                embed.add_field(
                    name="⚙️ Oyun Etkileri", value="\n".join(etki_listesi), inline=False
                )

        # Tarih
        tarih = current.get("date", "")
        if tarih:
            embed.set_footer(text=f"Son guncelleme: {tarih}")

        await self._send(ctx, embed=embed)

    # ==================================================================
    # /hava-durumu-gecmisi (bonus)
    # ==================================================================
    @commands.hybrid_command(
        name="hava-durumu-gecmisi", description="Son hava durumu kayitlarini gosterir"
    )
    @app_commands.describe(limit="Kac kayit (max 10)")
    async def hava_durumu_gecmisi_slash(self, ctx: commands.Context, limit: int = 5):
        """Son hava durumu kayitlarini gosterir."""
        if limit > 10:
            limit = 10
        if limit <= 0:
            limit = 5

        # DB'den son N kayit
        async with db._lock:
            cur = await db._conn.execute(
                "SELECT date, condition, effects FROM weather ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()

        if not rows:
            await self._send(ctx, 
                embed=embeds.info_embed(
                    "Hava Durumu Gecmisi", "Henuz hava durumu kaydi yok."
                )
            )
            return

        embed = discord.Embed(
            title="🌦️ Hava Durumu Gecmisi",
            description=f"Son {len(rows)} kayit:",
            color=config.RENK_BILGI,
        )

        for row in rows:
            tarih, durum, _ = row
            hava_bilgi = HAVA_DURUMLARI.get(durum, {})
            embed.add_field(
                name=f"{hava_bilgi.get('emoji', '🌦️')} {hava_bilgi.get('isim', durum)}",
                value=f"Tarih: {tarih}",
                inline=False,
            )

        await self._send(ctx, embed=embed)


# ==================================================================
# SETUP
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

async def setup(bot: commands.Bot):
    await bot.add_cog(HavaDurumuCog(bot))
    logger.info("HavaDurumuCog yuklendi")
