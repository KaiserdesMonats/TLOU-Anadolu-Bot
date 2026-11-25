"""
utils/checks.py - Yetki kontrol dekoratörleri ve yardimcilari.
discord.py ile uyumlu, cog'larda kullanilir.
"""
import functools
from datetime import datetime
from typing import Callable, Set
import discord
from discord import app_commands
from discord.ext import commands
import config
from utils.constants import TZ_ISTANBUL


def has_any_role_id(member: discord.Member, role_ids: Set[int]) -> bool:
    """Kullanicinin herhangi bir role sahip olup olmadigini kontrol et."""
    if not member:
        return False
    member_role_ids = {r.id for r in member.roles}
    return bool(member_role_ids & role_ids)


def is_admin(member: discord.Member) -> bool:
    """Admin yetkisi kontrolü (Yönetici Ekip)."""
    return has_any_role_id(member, config.ADMIN_ROLES)


def is_rp_yetkili(member: discord.Member) -> bool:
    """RP Yetkilisi yetkisi kontrolü (adminler otomatik dahil)."""
    return has_any_role_id(member, config.RP_YETKILI_ROLES)


def is_kayit_yetkili(member: discord.Member) -> bool:
    """Kayıt Yetkilisi yetkisi kontrolü (adminler otomatik dahil)."""
    return has_any_role_id(member, config.KAYIT_YETKILI_ROLES)


def is_gozlemci(member: discord.Member) -> bool:
    """Kullanıcı gözlemci mi? (Kayıtsız rolü yoksa ve Üye rolü varsa)"""
    if not member:
        return False
    role_ids = {r.id for r in member.roles}
    return (config.ROL_KAYITSIZ not in role_ids and
            config.ROL_UYE not in role_ids)


def is_kayitli(member: discord.Member) -> bool:
    """Kullanıcı kayıtlı mı? (Üye rolü varsa)"""
    if not member:
        return False
    return config.ROL_UYE in {r.id for r in member.roles}


# ==================================================================
# DECORATOR'LER (cog komutlarda kullanilir)
# ==================================================================
def admin_only():
    """Sadece adminlerin kullanabilecegi komutlar icin dekorator."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not is_admin(interaction.user):
            raise app_commands.MissingPermissions(["Admin yetkisi"])
        return True
    return app_commands.check(predicate)


def rp_yetkili_only():
    """RP yetkilisi ve adminler kullanabilir."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not is_rp_yetkili(interaction.user):
            raise app_commands.MissingPermissions(["RP Yetkilisi"])
        return True
    return app_commands.check(predicate)


def kayit_yetkili_only():
    """Kayit yetkilisi ve adminler kullanabilir."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not is_kayit_yetkili(interaction.user):
            raise app_commands.MissingPermissions(["Kayit Yetkilisi"])
        return True
    return app_commands.check(predicate)


def kayitli_only():
    """Kayitli kullanicilar kullanabilir (Üye rolü)."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            return False
        if not is_kayitli(interaction.user):
            raise app_commands.MissingPermissions(["Kayitli üye"])
        return True
    return app_commands.check(predicate)


def in_channel(channel_ids: Set[int]):
    """Komut sadece belirli kanallarda calisir."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.channel:
            return False
        if interaction.channel_id not in channel_ids:
            from utils.embeds import error_embed
            embed = error_embed("Yanlis Kanal",
                                "Bu komut bu kanalda kullanilamaz.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


def in_rp_category():
    """Komut sadece RP kategorilerindeki kanallarda calisir."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
            return False
        if not interaction.channel.category_id:
            return False
        if interaction.channel.category_id not in config.RP_KATEGORILERI:
            from utils.embeds import error_embed
            embed = error_embed("Yanlis Kanal",
                                "Bu komut sadece RP lokasyon kanallarinda kullanilir "
                                "(sehirler, tehlikeli bolgeler, vb.).")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)


def is_night_time() -> bool:
    """Gece saatlerinde miyiz? (21:00 sonrasi) - bot mesaj atmamak icin."""
    now = datetime.now(TZ_ISTANBUL)
    return now.hour >= config.GEC_BOT_SAATI or now.hour < 6
