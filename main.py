"""
main.py - TLOU Anadolu Bot Ana Baslatma Dosyasi
Botu Discord'a baglar, cog'lari yukler, event handler'lari kurar.
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import db

# ==================================================================
# LOGGING AYARLARI
# ==================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("tlo.main")

# ==================================================================
# INTENTS (Discord Developer Portal'da acik olmali)
# ==================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ==================================================================
# BOT INSTANCE
# ==================================================================
class TLOUBot(commands.Bot):
    """Ozel bot sinifi. Hybrid komut destegi."""

    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(config.PREFIX),
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
        )

    async def setup_hook(self):
        """Bot baslamadan once calisir. Veritabani ve cog'lar hazirlanir."""
        logger.info("Veritabani baglantisi kuruluyor...")
        await db.connect()
        logger.info("Veritabani hazir.")

        # Cog'lari yukle
        cog_list = [
            "cogs.kayit",
            "cogs.profil",
            "cogs.envanter",
            "cogs.meslek",
            "cogs.yagma",
            "cogs.uretim",
            "cogs.enfeksiyon",
            "cogs.cete",
            "cogs.event",
            "cogs.admin",
            "cogs.hava_durumu",
            "cogs.tasks",
            "cogs.yardim",
        ]
        for cog in cog_list:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog yuklendi: {cog}")
            except Exception as e:
                logger.error(f"Cog yuklenemedi: {cog} - {e}")

        # Komut sayisini logla
        logger.info(f"Toplam prefix komut sayisi: {len(self.commands)}")
        logger.info(f"Tree komut sayisi (setup_hook): {len(self.tree.get_commands())}")

        # tree.sync() setup_hook'ta calismiyor (bot Discord'a bagli degil).
        # on_ready'de yapacagiz.

    async def close(self):
        """Bot kapanirken temizlik yap."""
        logger.info("Bot kapatiliyor...")
        await db.close()
        await super().close()


# ==================================================================
# GLOBAL BOT INSTANCE
# ==================================================================
bot = TLOUBot()

# ==================================================================
# EVENT HANDLER'LAR
# ==================================================================
@bot.event
async def on_ready():
    """Bot Discord'a baglandiginda calisir."""
    logger.info("=" * 60)
    logger.info(f"Bot adi: {bot.user.name}")
    logger.info(f"Bot ID: {bot.user.id}")
    logger.info(f"Prefix: {config.PREFIX}")
    logger.info(f"Guild ID: {config.GUILD_ID}")
    logger.info(f"Versiyon: {config.BOT_VERSIYON}")
    logger.info("=" * 60)

    # Bot durumu
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=config.BOT_DURUM_METNI
            )
        )
    except Exception as e:
        logger.warning(f"Durum ayarlanamadi: {e}")

    logger.info("Bot hazir!")

    # Komutlari senkronize et (on_ready'de kesin calisir)
    # Hybrid komutlar global tree'de. once global'i guild'e kopyala, sonra sync.
    try:
        guild = discord.Object(id=config.GUILD_ID)
        # Global komutlari guild'e kopyala (aninda gorunmesi icin)
        bot.tree.copy_global_to(guild=guild)
        # Guild'e sync et
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"on_ready: Synced {len(synced)} komut (guild)")
        logger.info(f"Tree'de toplam: {len(bot.tree.get_commands())} komut (global)")
        logger.info(f"Guild tree: {len(bot.tree.get_commands(guild=guild))} komut")
    except Exception as e:
        logger.error(f"on_ready sync hatasi: {e}")


@bot.event
async def on_member_join(member: discord.Member):
    """Yeni uye sunucuya katildiginda. Kayitsiz rolunu ver."""
    if member.guild.id != config.GUILD_ID:
        return
    try:
        role = member.guild.get_role(config.ROL_KAYITSIZ)
        if role:
            await member.add_roles(role, reason="Yeni uye - otomatik kayitsiz")
        # Giris-cikis kanalina mesaj
        kanal = bot.get_channel(config.KANAL_GIRIS_CIKIS)
        if kanal:
            await kanal.send(
                f"Hosgeldin {member.mention}! Kayit olmak icin "
                f"<#{config.KANAL_KAYIT_SOHBET}> kanalina gidip "
                f"`/kayit` komutunu kullan."
            )
    except Exception as e:
        logger.error(f"on_member_join hatasi: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    """Uye sunucudan ayrildiginda."""
    if member.guild.id != config.GUILD_ID:
        return
    try:
        kanal = bot.get_channel(config.KANAL_GIRIS_CIKIS)
        if kanal:
            await kanal.send(f"{member.mention} sunucudan ayrildi. Gorusmek uzere!")
    except Exception as e:
        logger.error(f"on_member_remove hatasi: {e}")


@bot.event
async def on_message(message: discord.Message):
    """Mesaj geldiginde. Komut islemesini tetikler."""
    # Bot kendi mesajlarini isleme
    if message.author.bot:
        return

    # Son RP kanali takibi (yankesicilik mekanigi icin)
    if message.guild and message.guild.id == config.GUILD_ID:
        category_id = getattr(message.channel, "category_id", None)
        if category_id is None:
            parent = getattr(message.channel, "parent", None)
            category_id = getattr(parent, "category_id", None)
        if category_id in config.RP_KATEGORILERI:
            try:
                await db.update_stats(
                    message.author.id,
                    last_message_channel=message.channel.id,
                    last_message_at=int(datetime.now(timezone.utc).timestamp())
                )
            except Exception:
                pass

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Prefix komut hatalari."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komutu kullanma yetkiniz yok.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {error}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Eksik arguman: {error.param.name}")
    else:
        logger.error(f"Komut hatasi: {ctx.command} - {error}")
        await ctx.send("❌ Komut calistirilirken bir hata olustu.")


@bot.event
async def on_app_command_error(interaction: discord.Interaction,
                                error: app_commands.AppCommandError):
    """Slash komut hatalari - 'uygulama cevap vermedi' hatasini onler."""
    import traceback
    error_msg = str(error)
    logger.error(f"Slash komut hatasi: {error_msg}")
    logger.error(traceback.format_exc())

    async def gonder(mesaj):
        try:
            if interaction.response.is_done():
                await interaction.followup.send(mesaj, ephemeral=True)
            else:
                await interaction.response.send_message(mesaj, ephemeral=True)
        except Exception:
            try:
                await interaction.channel.send(mesaj)
            except Exception:
                pass

    if isinstance(error, app_commands.MissingPermissions):
        await gonder("❌ Bu komutu kullanma yetkiniz yok.")
    elif isinstance(error, app_commands.CommandOnCooldown):
        await gonder(f"⏳ {error}")
    elif isinstance(error, app_commands.CheckFailure):
        await gonder("❌ Bu komutu burada kullanamazsiniz.")
    elif "Interaction has already been responded to" in error_msg:
        # Zaten yanitlandi, bir sey yapma
        pass
    else:
        await gonder(f"❌ Komut calistirilirken bir hata olustu.\n```\n{error_msg[:1500]}\n```")


# ==================================================================
# BASLATMA
# ==================================================================
async def main():
    """Botu baslat."""
    if not config.BOT_TOKEN or config.BOT_TOKEN == "0":
        logger.error("BOT_TOKEN .env dosyasinda tanimli degil!")
        sys.exit(1)
    if not config.GUILD_ID:
        logger.error("GUILD_ID .env dosyasinda tanimli degil!")
        sys.exit(1)

    # 7/24 Hosting: Flask web sunucusunu baslat (UptimeRobot icin)
    try:
        from keep_alive import keep_alive
        keep_alive()
        logger.info("Keep-alive web sunucusu baslatildi.")
    except Exception as e:
        logger.warning(f"keep_alive baslatilamadi (sesli degil): {e}")

    async with bot:
        try:
            await bot.start(config.BOT_TOKEN)
        except KeyboardInterrupt:
            logger.info("Bot kapatildi (KeyboardInterrupt).")
        except Exception as e:
            logger.critical(f"Bot baslatilamadi: {e}")
            sys.exit(1)


if __name__ == "__main__":
    # Windows icin asyncio policy
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

