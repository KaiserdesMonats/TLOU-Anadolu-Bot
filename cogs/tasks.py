"""
cogs/tasks.py - Arka Plan Gorevleri
- Acluk/susuzluk dusurme (her 2 saatte %5)
- Enfeksiyon ilerletme (4 asama, olum kontrolu)
- Cete pasif geliri (24 saatte 150 🪙)
- Permadeath karantina (3 gun sonra gercek silme)
- Baskin suresi kontrolu (12 saat sonra sonuc)
- Aktif baskin kontrolu
"""

import logging
import time
import random
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

import config
from database import db
from utils.constants import HAVA_DURUMLARI


logger = logging.getLogger("tlo.cogs.tasks")

TZ_ISTANBUL = timezone(timedelta(hours=3))


# ==================================================================
# COG SINIFI
# ==================================================================
class TasksCog(commands.Cog):
    """Arka plan gorevleri cog'i."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Gorevleri baslat
        self.acluk_susuzluk_gorevi.start()  # her 2 saat
        self.enfeksiyon_gorevi.start()  # her 30 dakika
        self.cete_pasif_gelir_gorevi.start()  # her 1 saat
        self.permadeath_gorevi.start()  # her 6 saat
        self.baskin_kontrol_gorevi.start()  # her 1 saat

    def cog_unload(self):
        """Cog kaldirilirken gorevleri durdur."""
        self.acluk_susuzluk_gorevi.cancel()
        self.enfeksiyon_gorevi.cancel()
        self.cete_pasif_gelir_gorevi.cancel()
        self.permadeath_gorevi.cancel()
        self.baskin_kontrol_gorevi.cancel()

    # ==================================================================
    # 1. ACLUK/SUSUZLUK DUSURME GOREVI (her 2 saat)
    # ==================================================================
    @tasks.loop(hours=2)
    async def acluk_susuzluk_gorevi(self):
        """Her 2 saatte acluk ve susuzluk -5 duser.
        Asiri sicak hava durumunda susuzluk ekstra -%20 (yani -6).
        Sifira dusen oyuncunun cani dusmeye baslar.
        """
        try:
            # Hava durumunu al
            weather = await db.get_current_weather()
            hava_durumu = weather.get("condition", "gunesli") if weather else "gunesli"
            hava_bilgi = HAVA_DURUMLARI.get(hava_durumu, {})
            etkiler = hava_bilgi.get("etkiler", {})

            # Susuzluk carpimi
            susuzluk_carpim = etkiler.get("susuzluk_dusus_carpani", 1.0)
            susuzluk_dusus = int(5 * susuzluk_carpim)
            acluk_dusus = 5

            # Tum aktif (olu olmayan, gozlemci olmayan) kullanicilari guncelle
            async with db._lock:
                # Acluk dusur (0'in altina inmez)
                await db._conn.execute(
                    "UPDATE users SET acluk = MAX(0, acluk - ?) "
                    "WHERE gozlemci=0 AND is_dead=0",
                    (acluk_dusus,),
                )
                # Susuzluk dusur
                await db._conn.execute(
                    "UPDATE users SET susuzluk = MAX(0, susuzluk - ?) "
                    "WHERE gozlemci=0 AND is_dead=0",
                    (susuzluk_dusus,),
                )
                # Acluk 0 ise can dusur
                await db._conn.execute(
                    "UPDATE users SET can = MAX(0, can - 5) "
                    "WHERE acluk=0 AND gozlemci=0 AND is_dead=0"
                )
                # Susuzluk 0 ise can dusur
                await db._conn.execute(
                    "UPDATE users SET can = MAX(0, can - 5) "
                    "WHERE susuzluk=0 AND gozlemci=0 AND is_dead=0"
                )
                await db._conn.commit()

            # Cani 0'a dusen karakterleri isaretle (olum)
            async with db._lock:
                cur = await db._conn.execute(
                    "SELECT user_id FROM users WHERE can=0 AND is_dead=0"
                )
                olu_kullanicilar = await cur.fetchall()

            for row in olu_kullanicilar:
                user_id = row[0]
                await db.mark_character_dead(user_id, "acluk/susuzluk - olum")
                logger.info(f"Karakter olu (acluk/susuzluk): {user_id}")

                # Discord'da rolleri guncelle
                await self._karakter_olu_rol(user_id)

            logger.debug("Acluk/susuzluk gorevi tamamlandi")

        except Exception as e:
            logger.error(f"Acluk/susuzluk gorevi hatasi: {e}")

    @acluk_susuzluk_gorevi.before_loop
    async def acluk_susuzluk_before(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # 2. ENFEKSIYON ILERLEME GOREVI (her 30 dakika)
    # ==================================================================
    @tasks.loop(minutes=30)
    async def enfeksiyon_gorevi(self):
        """Her 30 dakikada enfekte kullanicilar kontrol edilir.
        Asama ilerletme + sure dolunca olum.
        """
        try:
            enfekte_users = await db.get_enfekte_users()
            if not enfekte_users:
                return

            now = int(time.time())
            asama_suresi = config.ENFEKSIYON_ASAMA_SURESI

            for row in enfekte_users:
                user_id, toplam_sure, baslangic, seviye = row
                gecen = now - baslangic

                # Sure doldu mu?
                if gecen >= toplam_sure:
                    # Enfeksiyon tamamlandi - olum
                    await db.mark_character_dead(
                        user_id, "enfeksiyon - zombilesme tamamlandi"
                    )
                    await self._karakter_olu_rol(user_id)
                    logger.info(f"Karakter olu (enfeksiyon): {user_id}")

                    # Enfeksiyon log kanalina bildiri
                    await self._enfeksiyon_olum_log(user_id)
                    continue

                # Asama ilerlemesi kontrol
                # Asama sinirlari: 0-18h asama 1, 18-36h asama 2, vb.
                yeni_seviye = min(4, (gecen // asama_suresi) + 1)

                if yeni_seviye > seviye:
                    # Asama atlandi - kullaniciya ve log'a bildiri
                    # FIX: Sadece seviye guncellenir; enfeksiyon_baslangic ve
                    # toplam sure sabit kaliyor. Eski kod baslangici her
                    # asamada sifirladigi icin gecen sure sifirdan sayiliyor
                    # ve (gecen // asama_suresi) + 1 hesabi 3. asamadan
                    # sonrasini hic tetiklemiyordu.
                    async with db._lock:
                        await db._conn.execute(
                            "UPDATE users SET enfeksiyon_seviye=? WHERE user_id=?",
                            (yeni_seviye, user_id),
                        )
                        await db._conn.commit()

                    logger.info(
                        f"Enfeksiyon asama ilerledi: user {user_id} "
                        f"{seviye} -> {yeni_seviye}"
                    )

                    # Enfeksiyon log kanalina bildiri
                    await self._enfeksiyon_asama_log(user_id, seviye, yeni_seviye)

        except Exception as e:
            logger.error(f"Enfeksiyon gorevi hatasi: {e}")

    @enfeksiyon_gorevi.before_loop
    async def enfeksiyon_before(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # 3. CETE PASIF GELIR GOREVI (her 1 saat)
    # ==================================================================
    @tasks.loop(hours=1)
    async def cete_pasif_gelir_gorevi(self):
        """Her saatte tüm cete kontrol edilir.
        24 saat gecmisse 150 🪙 pasif gelir eklenir.
        """
        try:
            # Tum onayli ceteleri getir
            gangs = await db.get_all_approved_gangs()
            now = int(time.time())

            for gang in gangs:
                gang_id = gang["id"]
                last = gang.get("passive_income_at", 0) or 0
                gecen = now - last

                if gecen >= config.CETE_PASIF_GELIR_ARALIK:
                    # Pasif gelir ekle
                    await db.add_passive_income(gang_id)
                    logger.info(f"Cete pasif gelir eklendi: {gang['name']} +150 🪙")

                    # Cete kasa log kanalina bildiri
                    await self._cete_pasif_log(gang)

        except Exception as e:
            logger.error(f"Cete pasif gelir gorevi hatasi: {e}")

    @cete_pasif_gelir_gorevi.before_loop
    async def cete_pasif_before(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # 4. PERMADEATH KARANTINA GOREVI (her 6 saat)
    # ==================================================================
    @tasks.loop(hours=6)
    async def permadeath_gorevi(self):
        """Olu karakterlerin karantina suresi (3 gun) dolmus mu kontrol et.
        Dolanlari gercekten sil (gozlemciye cevir).
        """
        try:
            # 3 gunden eski olu karakterleri getir
            dead_chars = await db.get_dead_characters(
                older_than_days=config.PERMADEATH_KARANTINA_GUN
            )

            if not dead_chars:
                return

            for char in dead_chars:
                user_id = char["user_id"]
                # Gercek silme - gozlemciye cevir
                await db.permanently_delete_character(user_id)
                logger.info(
                    f"Permadeath: Karakter gercekten silindi (user_id={user_id})"
                )

                # Admin log kanalina bildiri
                await self._permadeath_log(char)

        except Exception as e:
            logger.error(f"Permadeath gorevi hatasi: {e}")

    @permadeath_gorevi.before_loop
    async def permadeath_before(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # 5. BASKIN KONTROL GOREVI (her 1 saat)
    # ==================================================================
    @tasks.loop(hours=1)
    async def baskin_kontrol_gorevi(self):
        """Aktif baskinlarin suresi dolmus mu kontrol et.
        Dolan baskinlarin sonucunu hesapla.
        """
        try:
            active_raids = await db.get_all_active_raids()
            now = int(time.time())

            for raid in active_raids:
                end_time = raid.get("end_time", 0)
                if end_time > now:
                    continue  # henuz sure dolmadi

                # Sure doldu - sonuc hesapla
                await self._baskin_sonuc_hesapla(raid)

        except Exception as e:
            logger.error(f"Baskin kontrol gorevi hatasi: {e}")

    @baskin_kontrol_gorevi.before_loop
    async def baskin_before(self):
        await self.bot.wait_until_ready()

    # ==================================================================
    # YARDIMCI: BASKIN SONUC HESAPLAMA
    # ==================================================================
    async def _baskin_sonuc_hesapla(self, raid: dict):
        """Baskin sonucunu hesapla.
        Hesaplama:
        1. Saldiran ve savunan cetelerin aktif uye sayisi
        2. Saldiranin harcadigi cephane (önceden kesilmisti)
        3. Guç puani = uye_sayisi * 10 + rastgele(0-50)
        4. Admin onayi beklenmez (otomatik), RP kalitesi admin tarafindan
           sonradan duzeltilebilir (manuel /admin-baskin-duzelt)
        """
        raid_id = raid["id"]
        attacker_id = raid["attacker_gang"]
        defender_id = raid["defender_gang"]
        channel_id = raid.get("channel_id")

        # Aktif uye sayilari
        attacker_count = await db.get_active_member_count(attacker_id)
        defender_count = await db.get_active_member_count(defender_id)

        # Guç puani (uye * 10 + rastgele)
        attacker_power = attacker_count * 10 + random.randint(0, 50)
        defender_power = defender_count * 10 + random.randint(0, 50)

        # Kazanani belirle
        if attacker_power > defender_power:
            winner_id = attacker_id
            loser_id = defender_id
            saldiran_kazandi = True
        elif defender_power > attacker_power:
            winner_id = defender_id
            loser_id = attacker_id
            saldiran_kazandi = False
        else:
            # Beraberlik - savunan kazanir sayilir
            winner_id = defender_id
            loser_id = attacker_id
            saldiran_kazandi = False

        # Baskin durumunu guncelle
        await db.update_raid_status(raid_id, "completed", winner_id)

        # Kazanan, kaybedenin kasasindan %30 alir
        loser_gang = await db.get_gang_by_id(loser_id)
        if loser_gang:
            ganimet_para = int(
                loser_gang.get("money", 0) * config.CETE_BASKIN_GANIMET_ORANI
            )
            if ganimet_para > 0:
                await db.update_gang_money(loser_id, -ganimet_para)
                await db.update_gang_money(winner_id, ganimet_para)

                # Kaybedenin kasa envanterinden de %30 al
                loser_inv = await db.get_gang_inventory(loser_id)
                for item in loser_inv:
                    ganimet_miktar = int(
                        item["amount"] * config.CETE_BASKIN_GANIMET_ORANI
                    )
                    if ganimet_miktar > 0:
                        await db.remove_gang_item(
                            loser_id, item["item"], ganimet_miktar
                        )
                        await db.add_gang_item(winner_id, item["item"], ganimet_miktar)

        # Bolge kontrolunu degistir (kazanan alir, 3 RP gunu = 3 gun)
        if channel_id and saldiran_kazandi:
            await db.set_territory_owner(channel_id, attacker_id)
            # Kanal topic guncelle
            guild = self.bot.get_guild(config.GUILD_ID)
            if guild:
                kanal = guild.get_channel(channel_id)
                if kanal:
                    attacker_gang = await db.get_gang_by_id(attacker_id)
                    try:
                        await kanal.edit(
                            topic=f"🏴 Kontrol: {attacker_gang['name'] if attacker_gang else '?'}"
                        )
                    except discord.Forbidden:
                        pass
                    except Exception:
                        pass

        # Bolge-savaslari kanalina sonuc bildirisi
        guild = self.bot.get_guild(config.GUILD_ID)
        if guild:
            savas_kanal = guild.get_channel(config.KANAL_BOLGE_SAVASLARI)
            if savas_kanal:
                attacker_gang = await db.get_gang_by_id(attacker_id)
                defender_gang = await db.get_gang_by_id(defender_id)
                winner_gang = await db.get_gang_by_id(winner_id)

                embed = discord.Embed(
                    title="⚔️ Baskin Sonucu",
                    description=(
                        f"**Saldiran:** {attacker_gang['name'] if attacker_gang else '?'}\n"
                        f"**Savunan:** {defender_gang['name'] if defender_gang else '?'}\n"
                        f"**Kazanan:** {winner_gang['name'] if winner_gang else '?'}\n\n"
                        f"**Guç Puani:**\n"
                        f"• Saldiran: {attacker_power} (üye: {attacker_count})\n"
                        f"• Savunan: {defender_power} (üye: {defender_count})\n\n"
                        f"**Ganimet:** {ganimet_para if loser_gang else 0} 🪙 + esyalar"
                    ),
                    color=config.RENK_CETE,
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(
                    text=f"Baskin ID: {raid_id} | "
                    f"Admin RP kalitesi duzeltmesi icin: /admin-baskin-duzelt"
                )
                try:
                    await savas_kanal.send(embed=embed)
                except Exception as e:
                    logger.error(f"bolge-savaslari gonderilemedi: {e}")

            # Admin log
            admin_log = guild.get_channel(config.KANAL_ADMIN_LOG)
            if admin_log:
                log_embed = discord.Embed(
                    title="⚔️ Baskin Otomatik Sonuc",
                    description=f"Baskin ID: {raid_id}",
                    color=config.RENK_BILGI,
                    timestamp=discord.utils.utcnow(),
                )
                try:
                    await admin_log.send(embed=log_embed)
                except Exception:
                    pass

    # ==================================================================
    # YARDIMCI: KARAKTER OLU ROL GUNCELLEME
    # ==================================================================
    async def _karakter_olu_rol(self, user_id: int):
        """Olu karakterin rollerini guncelle.
        Tum meslek/sehir/cete rollerini al, Kayitsiz rolunu ver.
        """
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        member = guild.get_member(user_id)
        if not member:
            return

        # Tüm meslek/sehir/cete rollerini al
        tum_roller_id = set()
        tum_roller_id.update(config.SEHIR_ROLLERI.values())
        for grup in config.MESLEK_GRUPLARI.values():
            for _, rol_id in grup:
                tum_roller_id.add(rol_id)
        tum_roller_id.update(config.CETE_LIDER_ROLLERI.values())
        tum_roller_id.update(config.CETE_UYE_ROLLERI.values())

        kaldirilacak = []
        for rol_id in tum_roller_id:
            rol = guild.get_role(rol_id)
            if rol and rol in member.roles:
                kaldirilacak.append(rol)

        # Uye rolunu de al
        uye = guild.get_role(config.ROL_UYE)
        if uye and uye in member.roles:
            kaldirilacak.append(uye)

        if kaldirilacak:
            try:
                await member.remove_roles(*kaldirilacak, reason="Karakter olu")
            except discord.Forbidden:
                pass

        # Kayitsiz rolunu ver
        kayitsiz = guild.get_role(config.ROL_KAYITSIZ)
        if kayitsiz and kayitsiz not in member.roles:
            try:
                await member.add_roles(kayitsiz, reason="Karakter olu")
            except discord.Forbidden:
                pass

        # Nick degistir
        try:
            await member.edit(
                nick=f"💀 {member.display_name[:30]}", reason="Karakter olu"
            )
        except discord.Forbidden:
            pass

    # ==================================================================
    # YARDIMCI: ENFEKSIYON OLUM LOG
    # ==================================================================
    async def _enfeksiyon_olum_log(self, user_id: int):
        """Enfeksiyon sonrasi olumu log kanalina bildir."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        kanal = guild.get_channel(config.KANAL_ENFEKSIYON_LOG)
        if not kanal:
            return

        user_data = await db.get_user(user_id)
        isim = user_data.get("isim", "?") if user_data else "?"
        soyisim = user_data.get("soyisim", "") if user_data else ""
        tam_isim = f"{isim} {soyisim}".strip()

        embed = discord.Embed(
            title="💀 Enfeksiyon - Karakter Olumu",
            description=(
                f"**Karakter:** {tam_isim}\n"
                f"**Kullanici:** <@{user_id}>\n"
                f"**Sebep:** Enfeksiyon 4. asama tamamlandi - zombilesme\n\n"
                f"Karakter 3 gunluk karantinaya alindi.\n"
                f"Bu sure içinde itiraz edilmezse verileri kalici olarak silinecek.\n"
                f"Admin itiraz kabul ederse `/admin-canlandir` ile geri getirilebilir."
            ),
            color=config.RENK_Olum,
            timestamp=discord.utils.utcnow(),
        )
        try:
            await kanal.send(embed=embed)
        except Exception:
            pass

    # ==================================================================
    # YARDIMCI: ENFEKSIYON ASAMA LOG
    # ==================================================================
    async def _enfeksiyon_asama_log(
        self, user_id: int, eski_seviye: int, yeni_seviye: int
    ):
        """Enfeksiyon asama atlamasi log."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        kanal = guild.get_channel(config.KANAL_ENFEKSIYON_LOG)
        if not kanal:
            return

        asama_ad = config.ENFEKSIYON_ASAMA_ISIMLERI.get(yeni_seviye, "?")

        embed = discord.Embed(
            title="🦠 Enfeksiyon Asama Atladi",
            description=(
                f"**Kullanici:** <@{user_id}>\n"
                f"**Onceki Asama:** {eski_seviye}/4\n"
                f"**Yeni Asama:** {yeni_seviye}/4 - {asama_ad}\n\n"
                f"⚠️ Karakterin durumu kotulesiyor. Doktora basvur!"
            ),
            color=config.RENK_ENFEKSIYON,
            timestamp=discord.utils.utcnow(),
        )
        try:
            await kanal.send(embed=embed)
        except Exception:
            pass

    # ==================================================================
    # YARDIMCI: CETE PASIF GELIR LOG
    # ==================================================================
    async def _cete_pasif_log(self, gang: dict):
        """Cete pasif gelir log."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        kanal = guild.get_channel(config.KANAL_CETE_KASA_LOG)
        if not kanal:
            return

        embed = discord.Embed(
            title="💰 Çete Pasif Gelir",
            description=(
                f"**Çete:** {gang.get('name', '?')}\n"
                f"**Tür:** {gang.get('type', '?')}\n"
                f"**Miktar:** +{config.CETE_PASIF_GELIR} 🪙\n"
                f"**Yeni Kasa:** {gang.get('money', 0) + config.CETE_PASIF_GELIR} 🪙"
            ),
            color=config.RENK_KASA_YATIRMA,
            timestamp=discord.utils.utcnow(),
        )
        try:
            await kanal.send(embed=embed)
        except Exception:
            pass

    # ==================================================================
    # YARDIMCI: PERMADEATH LOG
    # ==================================================================
    async def _permadeath_log(self, char: dict):
        """Permadeath log."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        kanal = guild.get_channel(config.KANAL_ADMIN_LOG)
        if not kanal:
            return

        isim = char.get("isim", "?")
        soyisim = char.get("soyisim", "") or ""
        tam_isim = f"{isim} {soyisim}".strip()

        embed = discord.Embed(
            title="💀 Permadeath Tamamlandi",
            description=(
                f"**Karakter:** {tam_isim}\n"
                f"**User ID:** {char.get('user_id')}\n"
                f"**Sehir:** {char.get('sehir', '?')}\n"
                f"**Meslek:** {char.get('meslek', '?')}\n"
                f"**Olum Tarihi:** {char.get('death_date', '?')}\n\n"
                f"3 gunluk karantina suresi doldu.\n"
                f"Karakter verileri kalici olarak silindi, gozlemciye cevrildi."
            ),
            color=config.RENK_Olum,
            timestamp=discord.utils.utcnow(),
        )
        try:
            await kanal.send(embed=embed)
        except Exception:
            pass


# ==================================================================
# SETUP
# ==================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))
    logger.info("TasksCog yuklendi")
