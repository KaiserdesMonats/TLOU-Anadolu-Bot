"""
database.py - TLOU Anadolu Asenkron Veritabani Yoneticisi
aiosqlite kullanir. Kurulum gerektirmez, tek dosya (tlo_bot.db).
Tum cog'lar bu modulu import eder: from database import db
"""
import asyncio
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import aiosqlite
import config

logger = logging.getLogger("tlo.database")

# Istanbul saat dilimi (UTC+3)
TZ_ISTANBUL = timezone(timedelta(hours=3))


class Database:
    """Asenkron SQLite veritabani yoneticisi."""

    def __init__(self, db_path: str = config.DB_DOSYA_YOLU):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    # ==================================================================
    # BAGLANTI YONETIMI
    # ==================================================================
    async def connect(self):
        """Bot baslangicinda cagrilir. Baglanti kurar ve tablolari olusturur."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.commit()
        await self.create_tables()
        logger.info(f"Veritabani baglandi: {self.db_path}")

    async def close(self):
        """Bot kapanirken cagrilir."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Veritabani baglantisi kapatildi.")

    async def create_tables(self):
        """Tum tablolari olusturur (IF NOT EXISTS)."""
        async with self._lock:
            await self._conn.executescript('''
                -- USERS: Karakter verileri
                CREATE TABLE IF NOT EXISTS users (
                    user_id              INTEGER PRIMARY KEY,
                    isim                 TEXT,
                    soyisim              TEXT,
                    yas                  INTEGER,
                    sehir                TEXT,
                    meslek               TEXT,
                    can                  INTEGER DEFAULT 100,
                    acluk                INTEGER DEFAULT 100,
                    susuzluk             INTEGER DEFAULT 100,
                    para                 INTEGER DEFAULT 100,
                    gozlemci             INTEGER DEFAULT 0,
                    is_dead              INTEGER DEFAULT 0,
                    death_date           TEXT,
                    kayit_tarihi         TEXT,
                    enfeksiyon_suresi    INTEGER DEFAULT 0,
                    enfeksiyon_baslangic INTEGER DEFAULT 0,
                    enfeksiyon_seviye    INTEGER DEFAULT 0,
                    slot_seviye          INTEGER DEFAULT 0,
                    last_message_channel INTEGER,
                    last_message_at      INTEGER
                );

                -- INVENTORY
                CREATE TABLE IF NOT EXISTS inventory (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    item_name   TEXT NOT NULL,
                    amount      INTEGER DEFAULT 1,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_inv_user ON inventory(user_id);
                -- add_item() ON CONFLICT(user_id, item_name) kullanir. Bu
                -- benzersiz indeks olmadan SQLite komutu calistirmaz.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_inv_user_item
                    ON inventory(user_id, item_name);

                -- COOLDOWNS
                CREATE TABLE IF NOT EXISTS cooldowns (
                    user_id      INTEGER NOT NULL,
                    command_type TEXT NOT NULL,
                    last_used_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, command_type)
                );

                -- GANGS
                CREATE TABLE IF NOT EXISTS gangs (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    name              TEXT UNIQUE NOT NULL,
                    type              TEXT NOT NULL,
                    leader_id         INTEGER NOT NULL,
                    money             INTEGER DEFAULT 0,
                    perks             TEXT,
                    approved          INTEGER DEFAULT 0,
                    created_at        TEXT,
                    passive_income_at INTEGER DEFAULT 0
                );

                -- GANG_MEMBERS
                CREATE TABLE IF NOT EXISTS gang_members (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    gang_id   INTEGER NOT NULL,
                    user_id   INTEGER NOT NULL UNIQUE,
                    role      TEXT DEFAULT 'uye',
                    join_date TEXT,
                    FOREIGN KEY(gang_id) REFERENCES gangs(id),
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_gm_gang ON gang_members(gang_id);

                -- GANG_INVENTORY
                CREATE TABLE IF NOT EXISTS gang_inventory (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    gang_id   INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    amount    INTEGER DEFAULT 1,
                    FOREIGN KEY(gang_id) REFERENCES gangs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_gi_gang ON gang_inventory(gang_id);
                -- add_gang_item() icin gerekli benzersiz anahtar.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_gi_gang_item
                    ON gang_inventory(gang_id, item_name);

                -- TERRITORY_CONTROL
                CREATE TABLE IF NOT EXISTS territory_control (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id    INTEGER UNIQUE NOT NULL,
                    gang_id       INTEGER,
                    control_date  TEXT,
                    locked        INTEGER DEFAULT 0,
                    locked_reason TEXT,
                    FOREIGN KEY(gang_id) REFERENCES gangs(id)
                );

                -- RAIDS
                CREATE TABLE IF NOT EXISTS raids (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    attacker_gang  INTEGER NOT NULL,
                    defender_gang  INTEGER NOT NULL,
                    channel_id     INTEGER,
                    status         TEXT DEFAULT 'ongoing',
                    start_time     INTEGER,
                    end_time       INTEGER,
                    winner_gang_id INTEGER,
                    FOREIGN KEY(attacker_gang) REFERENCES gangs(id),
                    FOREIGN KEY(defender_gang) REFERENCES gangs(id)
                );

                -- WEATHER
                CREATE TABLE IF NOT EXISTS weather (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    date      TEXT,
                    condition TEXT,
                    effects   TEXT
                );

                -- EVENT_LOG
                CREATE TABLE IF NOT EXISTS event_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    details    TEXT,
                    date       TEXT,
                    channel_id INTEGER
                );

                -- ACTIVE_EVENTS
                CREATE TABLE IF NOT EXISTS active_events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type   TEXT NOT NULL,
                    channel_id   INTEGER,
                    start_time   INTEGER NOT NULL,
                    end_time     INTEGER NOT NULL,
                    data         TEXT,
                    completed    INTEGER DEFAULT 0
                );

                -- ACTION_LOGS
                CREATE TABLE IF NOT EXISTS action_logs (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_type  TEXT NOT NULL,
                    actor_id  INTEGER,
                    target_id INTEGER,
                    action    TEXT,
                    details   TEXT,
                    timestamp INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_al_type ON action_logs(log_type, timestamp);

                -- TOMBSTONES (olen karakter arsivi)
                CREATE TABLE IF NOT EXISTS tombstones (
                    user_id      INTEGER PRIMARY KEY,
                    isim         TEXT,
                    soyisim      TEXT,
                    yas          INTEGER,
                    sehir        TEXT,
                    meslek       TEXT,
                    death_date   TEXT,
                    death_reason TEXT
                );
            ''')
            await self._conn.commit()

    # ==================================================================
    # KAYIT / USER YONETIMI
    # ==================================================================
    async def complete_gozlemci_kayit(self, user_id: int, isim: str) -> bool:
        """Gozlemci kaydini DB'ye isle."""
        async with self._lock:
            now_iso = datetime.now(TZ_ISTANBUL).isoformat()
            await self._conn.execute(
                """INSERT INTO users (user_id, isim, soyisim, yas, sehir, meslek,
                                       can, acluk, susuzluk, para, gozlemci, kayit_tarihi)
                   VALUES (?, ?, NULL, NULL, NULL, 'Gozlemci',
                           100, 100, 100, 0, 1, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       isim=excluded.isim, soyisim=NULL, yas=NULL,
                       sehir=NULL, meslek='Gozlemci', gozlemci=1,
                       is_dead=0, death_date=NULL,
                       enfeksiyon_suresi=0, enfeksiyon_baslangic=0, enfeksiyon_seviye=0,
                       para=100, can=100, acluk=100, susuzluk=100""",
                (user_id, isim, now_iso)
            )
            await self._conn.commit()
            return True

    async def complete_rp_kayit(self, user_id: int, isim: str, soyisim: str,
                                yas: int, sehir: str, meslek: str) -> bool:
        """RP oyuncusu kaydini DB'ye isle."""
        async with self._lock:
            now_iso = datetime.now(TZ_ISTANBUL).isoformat()
            await self._conn.execute(
                """INSERT INTO users (user_id, isim, soyisim, yas, sehir, meslek,
                                       can, acluk, susuzluk, para, gozlemci, kayit_tarihi)
                   VALUES (?, ?, ?, ?, ?, ?,
                           100, 100, 100, 100, 0, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       isim=excluded.isim, soyisim=excluded.soyisim, yas=excluded.yas,
                       sehir=excluded.sehir, meslek=excluded.meslek, gozlemci=0,
                       is_dead=0, death_date=NULL,
                       enfeksiyon_suresi=0, enfeksiyon_baslangic=0, enfeksiyon_seviye=0,
                       para=100, can=100, acluk=100, susuzluk=100""",
                (user_id, isim, soyisim, yas, sehir, meslek, now_iso)
            )
            await self._conn.commit()
            return True

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Kullanicinin tum verisini dict olarak getir."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM users WHERE user_id=?",
                (user_id,)
            )
            row = await cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    async def update_stats(self, user_id: int, **kwargs):
        """Kullanici istatistiklerini guncelle.
        Ornek: update_stats(user_id, can=-10, para='+50')
        """
        if not kwargs:
            return
        valid_cols = {'can', 'acluk', 'susuzluk', 'para', 'isim', 'soyisim', 'yas',
                      'sehir', 'meslek', 'slot_seviye', 'last_message_channel', 'last_message_at'}
        sets, vals = [], []
        for k, v in kwargs.items():
            if k not in valid_cols:
                continue
            if k in {'can', 'acluk', 'susuzluk', 'para'} and isinstance(v, str) and v.startswith(('+', '-')):
                sets.append(f"{k} = {k} + ?")
                vals.append(int(v))
            else:
                sets.append(f"{k} = ?")
                vals.append(v)
        if not sets:
            return
        vals.append(user_id)
        async with self._lock:
            await self._conn.execute(
                f"UPDATE users SET {', '.join(sets)} WHERE user_id=?",
                vals
            )
            await self._conn.commit()

    async def update_money(self, user_id: int, amount: int):
        """Para ekle/cikar (negatif = cek)."""
        async with self._lock:
            await self._conn.execute(
                "UPDATE users SET para = MAX(0, para + ?) WHERE user_id=?",
                (amount, user_id)
            )
            await self._conn.commit()

    # ==================================================================
    # ENVANTER
    # ==================================================================
    async def add_item(self, user_id: int, item_name: str, amount: int = 1):
        """Envantere esya ekle (varsa guncelle)."""
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO inventory (user_id, item_name, amount)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, item_name) DO UPDATE SET
                       amount = amount + ?""",
                (user_id, item_name, amount, amount)
            )
            await self._conn.commit()

    async def remove_item(self, user_id: int, item_name: str, amount: int = 1) -> bool:
        """Envanterden esya cikar. Yeterli yoksa False doner."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT amount FROM inventory WHERE user_id=? AND item_name=?",
                (user_id, item_name)
            )
            row = await cur.fetchone()
            if not row or row[0] < amount:
                return False
            new_amount = row[0] - amount
            if new_amount <= 0:
                await self._conn.execute(
                    "DELETE FROM inventory WHERE user_id=? AND item_name=?",
                    (user_id, item_name)
                )
            else:
                await self._conn.execute(
                    "UPDATE inventory SET amount=? WHERE user_id=? AND item_name=?",
                    (new_amount, user_id, item_name)
                )
            await self._conn.commit()
            return True

    async def has_item(self, user_id: int, item_name: str, amount: int = 1) -> bool:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT amount FROM inventory WHERE user_id=? AND item_name=?",
                (user_id, item_name)
            )
            row = await cur.fetchone()
        return row is not None and row[0] >= amount

    async def get_inventory(self, user_id: int) -> list:
        """Envanteri listele."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT item_name, amount FROM inventory WHERE user_id=? ORDER BY item_name",
                (user_id,)
            )
            rows = await cur.fetchall()
        return [{"item": r[0], "amount": r[1]} for r in rows]

    async def get_inventory_count(self, user_id: int) -> int:
        """Envanterdeki toplam esya adedi (slot doluluk hesabi icin)."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT SUM(amount) FROM inventory WHERE user_id=?",
                (user_id,)
            )
            row = await cur.fetchone()
        return row[0] if row and row[0] else 0

    async def get_slot_capacity(self, user_id: int) -> int:
        """Kullanicinin slot kapasitesi."""
        user = await self.get_user(user_id)
        if not user:
            return config.BASLANGIC_SLOT
        sev = user.get('slot_seviye', 0)
        if sev <= 0:
            return config.BASLANGIC_SLOT
        if sev <= len(config.SLOT_GELISTIRME_SEVIYELERI):
            return config.SLOT_GELISTIRME_SEVIYELERI[sev - 1][0]
        return config.SLOT_GELISTIRME_SEVIYELERI[-1][0]

    async def upgrade_slot(self, user_id: int) -> tuple:
        """Slot gelistir. Returns (success, message, cost)."""
        user = await self.get_user(user_id)
        if not user:
            return False, "Kullanici bulunamadi.", 0
        sev = user.get('slot_seviye', 0)
        if sev >= len(config.SLOT_GELISTIRME_SEVIYELERI):
            return False, "Maksimum slot seviyesine ulasilmis.", 0
        cost = config.SLOT_GELISTIRME_SEVIYELERI[sev][1]
        if user['para'] < cost:
            return False, f"Yetersiz para. Gereken: {cost} 🪙", cost
        async with self._lock:
            await self._conn.execute(
                "UPDATE users SET para = para - ?, slot_seviye = slot_seviye + 1 WHERE user_id=?",
                (cost, user_id)
            )
            await self._conn.commit()
        return True, "Slot gelistirildi.", cost

    # ==================================================================
    # COOLDOWN
    # ==================================================================
    async def get_cooldown(self, user_id: int, command_type: str) -> int:
        """Belirli bir komut icin kalan cooldown saniyesi (0 = hazir)."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT last_used_at FROM cooldowns WHERE user_id=? AND command_type=?",
                (user_id, command_type)
            )
            row = await cur.fetchone()
        if not row:
            return 0
        cd_map = {
            'yagma':           config.CD_YAGMA,
            'arastir':         config.CD_YAGMA,
            'enfekte-temizle': config.CD_YAGMA,
            'meslek':          config.CD_MESLEK,
            'yankesicilik':    config.CD_YANKESICILIK,
            'rituel':          config.CD_RITUEL,
        }
        cd_sure = cd_map.get(command_type, config.CD_MESLEK)
        elapsed = int(time.time()) - row[0]
        return max(0, cd_sure - elapsed)

    async def set_cooldown(self, user_id: int, command_type: str):
        """Cooldown baslat."""
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO cooldowns (user_id, command_type, last_used_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, command_type) DO UPDATE SET last_used_at=?""",
                (user_id, command_type, int(time.time()), int(time.time()))
            )
            await self._conn.commit()

    async def is_on_cooldown(self, user_id: int, command_type: str) -> bool:
        return (await self.get_cooldown(user_id, command_type)) > 0

    # ==================================================================
    # ACTION LOGS
    # ==================================================================
    async def add_action_log(self, log_type: str, actor_id: Optional[int],
                              target_id: Optional[int], action: str,
                              details: dict = None):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO action_logs (log_type, actor_id, target_id, action, details, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (log_type, actor_id, target_id, action,
                 json.dumps(details) if details else None, int(time.time()))
            )
            await self._conn.commit()

    async def get_logs(self, log_type: str, limit: int = 50) -> list:
        """Belirli turde log getir."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM action_logs WHERE log_type=? ORDER BY timestamp DESC LIMIT ?",
                (log_type, limit)
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get('details'):
                try:
                    d['details'] = json.loads(d['details'])
                except Exception:
                    pass
            results.append(d)
        return results

    # ==================================================================
    # HAVA DURUMU
    # ==================================================================
    async def set_weather(self, condition: str, effects: dict):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO weather (date, condition, effects)
                   VALUES (?, ?, ?)""",
                (datetime.now(TZ_ISTANBUL).isoformat(),
                 condition, json.dumps(effects))
            )
            await self._conn.commit()

    async def get_current_weather(self) -> Optional[dict]:
        """En son hava durumu kaydini getir."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM weather ORDER BY id DESC LIMIT 1"
            )
            row = await cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        d = dict(zip(cols, row))
        if d.get('effects'):
            try:
                d['effects'] = json.loads(d['effects'])
            except Exception:
                pass
        return d

    # ==================================================================
    # EVENTLER
    # ==================================================================
    async def add_event_log(self, event_type: str, details: dict, channel_id: int = None):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO event_log (event_type, details, date, channel_id)
                   VALUES (?, ?, ?, ?)""",
                (event_type, json.dumps(details),
                 datetime.now(TZ_ISTANBUL).isoformat(), channel_id)
            )
            await self._conn.commit()

    async def create_active_event(self, event_type: str, channel_id: int,
                                   duration: int, data: dict = None) -> int:
        """Aktif event olustur, ID'sini dondur."""
        now = int(time.time())
        async with self._lock:
            cur = await self._conn.execute(
                """INSERT INTO active_events (event_type, channel_id, start_time, end_time, data)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, channel_id, now, now + duration,
                 json.dumps(data) if data else None)
            )
            await self._conn.commit()
            return cur.lastrowid

    async def get_active_events(self) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM active_events WHERE completed=0 AND end_time > ?",
                (int(time.time()),)
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get('data'):
                try:
                    d['data'] = json.loads(d['data'])
                except Exception:
                    pass
            results.append(d)
        return results

    async def complete_active_event(self, event_id: int):
        async with self._lock:
            await self._conn.execute(
                "UPDATE active_events SET completed=1 WHERE id=?",
                (event_id,)
            )
            await self._conn.commit()

    async def get_last_event_time(self, event_type: str) -> int:
        """Belirli turdeki son event zamani (cooldown kontrolu icin)."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT MAX(start_time) FROM active_events WHERE event_type=?",
                (event_type,)
            )
            row = await cur.fetchone()
        return row[0] if row and row[0] else 0

    # ==================================================================
    # ENFEKSIYON
    # ==================================================================
    async def set_enfeksiyon(self, user_id: int, sure_saniye: int, seviye: int = 1):
        """Enfeksiyon baslat veya guncelle."""
        now = int(time.time())
        async with self._lock:
            await self._conn.execute(
                "UPDATE users SET enfeksiyon_suresi=?, enfeksiyon_baslangic=?, "
                "enfeksiyon_seviye=? WHERE user_id=?",
                (sure_saniye, now, seviye, user_id)
            )
            await self._conn.commit()

    async def extend_enfeksiyon(self, user_id: int, ek_saniye: int):
        """Doktor mudahalesiyle enfeksiyon suresini uzat (geciktirme)."""
        async with self._lock:
            await self._conn.execute(
                "UPDATE users SET enfeksiyon_suresi = enfeksiyon_suresi + ? WHERE user_id=?",
                (ek_saniye, user_id)
            )
            await self._conn.commit()

    async def clear_enfeksiyon(self, user_id: int):
        """Enfeksiyonu tamamen temizle (asi/doktor)."""
        async with self._lock:
            await self._conn.execute(
                "UPDATE users SET enfeksiyon_suresi=0, enfeksiyon_baslangic=0, "
                "enfeksiyon_seviye=0 WHERE user_id=?",
                (user_id,)
            )
            await self._conn.commit()

    async def get_enfeksiyon_durumu(self, user_id: int) -> dict:
        """Kullanicinin enfeksiyon durumunu dondur."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT enfeksiyon_suresi, enfeksiyon_baslangic, enfeksiyon_seviye "
                "FROM users WHERE user_id=?",
                (user_id,)
            )
            row = await cur.fetchone()
        if not row or not row[0] or not row[2]:
            return {"var": False, "seviye": 0, "kalan_sure": 0, "toplam_sure": 0}
        toplam, baslangic, seviye = row
        now = int(time.time())
        gecen = now - baslangic
        kalan = max(0, toplam - gecen)
        return {
            "var": kalan > 0,
            "seviye": seviye,
            "kalan_sure": kalan,
            "toplam_sure": toplam,
            "gecen_sure": gecen
        }

    async def get_enfekte_users(self) -> list:
        """Tum enfekte kullanicilari getir (tasks.py icin)."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT user_id, enfeksiyon_suresi, enfeksiyon_baslangic, enfeksiyon_seviye "
                "FROM users WHERE enfeksiyon_suresi > 0 AND enfeksiyon_seviye > 0 AND is_dead=0"
            )
            return await cur.fetchall()

    # ==================================================================
    # CETE SISTEMI
    # ==================================================================
    async def create_gang(self, name: str, gang_type: str, leader_id: int,
                          perks: list) -> int:
        """Yeni çete oluştur (approved=0, admin onayı bekler)."""
        async with self._lock:
            now_iso = datetime.now(TZ_ISTANBUL).isoformat()
            cur = await self._conn.execute(
                """INSERT INTO gangs (name, type, leader_id, perks, approved, created_at, passive_income_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)""",
                (name, gang_type, leader_id, json.dumps(perks), now_iso, int(time.time()))
            )
            await self._conn.commit()
            gang_id = cur.lastrowid
            # Lideri uye olarak ekle
            await self._conn.execute(
                """INSERT INTO gang_members (gang_id, user_id, role, join_date)
                   VALUES (?, ?, 'lider', ?)""",
                (gang_id, leader_id, now_iso)
            )
            await self._conn.commit()
            return gang_id

    async def get_gang_by_id(self, gang_id: int) -> Optional[dict]:
        async with self._lock:
            cur = await self._conn.execute("SELECT * FROM gangs WHERE id=?", (gang_id,))
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            if d.get('perks'):
                try:
                    d['perks'] = json.loads(d['perks'])
                except Exception:
                    d['perks'] = []
            return d

    async def get_gang_by_name(self, name: str) -> Optional[dict]:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM gangs WHERE name LIKE ? COLLATE NOCASE", (name,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            if d.get('perks'):
                try:
                    d['perks'] = json.loads(d['perks'])
                except Exception:
                    d['perks'] = []
            return d

    async def get_user_gang(self, user_id: int) -> Optional[dict]:
        """Kullanicinin cetesini getir."""
        async with self._lock:
            cur = await self._conn.execute(
                """SELECT g.id, g.name, g.type, g.leader_id, gm.role
                   FROM gang_members gm
                   JOIN gangs g ON gm.gang_id = g.id
                   WHERE gm.user_id=?""",
                (user_id,)
            )
            row = await cur.fetchone()
        if not row:
            return None
        return {"gang_id": row[0], "name": row[1], "type": row[2],
                "leader_id": row[3], "role": row[4]}

    async def get_gang_members(self, gang_id: int) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                """SELECT gm.user_id, gm.role, gm.join_date, u.isim, u.soyisim
                   FROM gang_members gm
                   JOIN users u ON gm.user_id = u.user_id
                   WHERE gm.gang_id=? ORDER BY gm.role DESC, gm.join_date ASC""",
                (gang_id,)
            )
            rows = await cur.fetchall()
        return [{"user_id": r[0], "role": r[1], "join_date": r[2],
                 "isim": r[3], "soyisim": r[4]} for r in rows]

    async def get_gang_leader(self, gang_id: int) -> Optional[int]:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT leader_id FROM gangs WHERE id=?", (gang_id,)
            )
            row = await cur.fetchone()
        return row[0] if row else None

    async def get_gang_member_count(self, gang_id: int) -> int:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT COUNT(*) FROM gang_members WHERE gang_id=?", (gang_id,)
            )
            row = await cur.fetchone()
        return row[0] if row else 0

    async def get_active_member_count(self, gang_id: int) -> int:
        """Aktif üye sayısı (is_dead=0 olanlar)."""
        async with self._lock:
            cur = await self._conn.execute(
                """SELECT COUNT(*) FROM gang_members gm
                   JOIN users u ON gm.user_id = u.user_id
                   WHERE gm.gang_id=? AND u.is_dead=0""",
                (gang_id,)
            )
            row = await cur.fetchone()
        return row[0] if row else 0

    async def add_gang_member(self, gang_id: int, user_id: int) -> bool:
        """Çeteye üye ekle. Üye başka çetede varsa False döner."""
        existing = await self.get_user_gang(user_id)
        if existing:
            return False
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO gang_members (gang_id, user_id, role, join_date)
                   VALUES (?, ?, 'uye', ?)""",
                (gang_id, user_id, datetime.now(TZ_ISTANBUL).isoformat())
            )
            await self._conn.commit()
        return True

    async def leave_gang(self, user_id: int):
        """Çeteden ayrıl."""
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM gang_members WHERE user_id=?",
                (user_id,)
            )
            await self._conn.commit()

    async def set_gang_member_role(self, user_id: int, role: str):
        """Üye rolünü güncelle (lider/subay/uye)."""
        async with self._lock:
            await self._conn.execute(
                "UPDATE gang_members SET role=? WHERE user_id=?",
                (role, user_id)
            )
            await self._conn.commit()

    async def count_approved_gangs_by_type(self, gang_type: str) -> int:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT COUNT(*) FROM gangs WHERE type=? AND approved=1",
                (gang_type,)
            )
            row = await cur.fetchone()
        return row[0] if row else 0

    async def get_all_approved_gangs(self) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM gangs WHERE approved=1 ORDER BY type, name"
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get('perks'):
                try:
                    d['perks'] = json.loads(d['perks'])
                except Exception:
                    d['perks'] = []
            results.append(d)
        return results

    async def get_pending_gangs(self) -> list:
        """Onay bekleyen çeteler."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM gangs WHERE approved=0 ORDER BY created_at"
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            if d.get('perks'):
                try:
                    d['perks'] = json.loads(d['perks'])
                except Exception:
                    d['perks'] = []
            results.append(d)
        return results

    async def approve_gang(self, gang_id: int):
        async with self._lock:
            await self._conn.execute(
                "UPDATE gangs SET approved=1 WHERE id=?", (gang_id,)
            )
            await self._conn.commit()

    async def reject_gang(self, gang_id: int):
        async with self._lock:
            await self._conn.execute("DELETE FROM gangs WHERE id=?", (gang_id,))
            await self._conn.execute(
                "DELETE FROM gang_members WHERE gang_id=?", (gang_id,))
            await self._conn.commit()

    async def disband_gang(self, gang_id: int):
        """Çeteyi zorla dagit (admin). Kasa silinir, uyelikler silinir."""
        async with self._lock:
            await self._conn.execute(
                "DELETE FROM gang_inventory WHERE gang_id=?", (gang_id,))
            await self._conn.execute(
                "DELETE FROM territory_control WHERE gang_id=?", (gang_id,))
            await self._conn.execute(
                "DELETE FROM gang_members WHERE gang_id=?", (gang_id,))
            await self._conn.execute("DELETE FROM gangs WHERE id=?", (gang_id,))
            await self._conn.commit()

    async def update_gang_money(self, gang_id: int, amount: int):
        async with self._lock:
            await self._conn.execute(
                "UPDATE gangs SET money = MAX(0, money + ?) WHERE id=?",
                (amount, gang_id)
            )
            await self._conn.commit()

    async def add_gang_item(self, gang_id: int, item_name: str, amount: int = 1):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO gang_inventory (gang_id, item_name, amount)
                   VALUES (?, ?, ?)
                   ON CONFLICT(gang_id, item_name) DO UPDATE SET amount = amount + ?""",
                (gang_id, item_name, amount, amount)
            )
            await self._conn.commit()

    async def remove_gang_item(self, gang_id: int, item_name: str, amount: int = 1) -> bool:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT amount FROM gang_inventory WHERE gang_id=? AND item_name=?",
                (gang_id, item_name)
            )
            row = await cur.fetchone()
            if not row or row[0] < amount:
                return False
            new_amount = row[0] - amount
            if new_amount <= 0:
                await self._conn.execute(
                    "DELETE FROM gang_inventory WHERE gang_id=? AND item_name=?",
                    (gang_id, item_name)
                )
            else:
                await self._conn.execute(
                    "UPDATE gang_inventory SET amount=? WHERE gang_id=? AND item_name=?",
                    (new_amount, gang_id, item_name)
                )
            await self._conn.commit()
            return True

    async def get_gang_inventory(self, gang_id: int) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT item_name, amount FROM gang_inventory WHERE gang_id=? ORDER BY item_name",
                (gang_id,)
            )
            rows = await cur.fetchall()
        return [{"item": r[0], "amount": r[1]} for r in rows]

    async def needs_passive_income(self, gang_id: int) -> bool:
        gang = await self.get_gang_by_id(gang_id)
        if not gang:
            return False
        last = gang.get('passive_income_at', 0) or 0
        return (int(time.time()) - last) >= config.CETE_PASIF_GELIR_ARALIK

    async def add_passive_income(self, gang_id: int):
        """Pasif gelir ekle (24 saatte bir)."""
        async with self._lock:
            await self._conn.execute(
                "UPDATE gangs SET money = money + ?, passive_income_at = ? WHERE id=?",
                (config.CETE_PASIF_GELIR, int(time.time()), gang_id)
            )
            await self._conn.commit()

    # ==================================================================
    # BOLGE KONTROLU
    # ==================================================================
    async def is_territory_locked(self, channel_id: int) -> tuple:
        """(locked, reason) dondur."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT locked, locked_reason FROM territory_control WHERE channel_id=?",
                (channel_id,)
            )
            row = await cur.fetchone()
        if not row:
            return False, None
        return bool(row[0]), row[1]

    async def lock_territory(self, channel_id: int, reason: str, gang_id: int = None):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO territory_control (channel_id, gang_id, control_date, locked, locked_reason)
                   VALUES (?, ?, ?, 1, ?)
                   ON CONFLICT(channel_id) DO UPDATE SET locked=1, locked_reason=?""",
                (channel_id, gang_id, datetime.now(TZ_ISTANBUL).isoformat(), reason, reason)
            )
            await self._conn.commit()

    async def unlock_territory(self, channel_id: int):
        async with self._lock:
            await self._conn.execute(
                "UPDATE territory_control SET locked=0, locked_reason=NULL WHERE channel_id=?",
                (channel_id,)
            )
            await self._conn.commit()

    async def get_territory_owner(self, channel_id: int) -> Optional[dict]:
        """Bolgenin sahibi ceteyi getir."""
        async with self._lock:
            cur = await self._conn.execute(
                """SELECT tc.gang_id, g.name, g.type
                   FROM territory_control tc
                   LEFT JOIN gangs g ON tc.gang_id = g.id
                   WHERE tc.channel_id=? AND tc.locked=0
                   ORDER BY tc.id DESC LIMIT 1""",
                (channel_id,)
            )
            row = await cur.fetchone()
        if not row or not row[0]:
            return None
        return {"gang_id": row[0], "name": row[1], "type": row[2]}

    async def set_territory_owner(self, channel_id: int, gang_id: int):
        async with self._lock:
            await self._conn.execute(
                """INSERT INTO territory_control (channel_id, gang_id, control_date, locked)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(channel_id) DO UPDATE SET gang_id=?, control_date=?""",
                (channel_id, gang_id, datetime.now(TZ_ISTANBUL).isoformat(),
                 gang_id, datetime.now(TZ_ISTANBUL).isoformat())
            )
            await self._conn.commit()

    async def clear_territory_owner(self, channel_id: int):
        async with self._lock:
            await self._conn.execute(
                "UPDATE territory_control SET gang_id=NULL WHERE channel_id=?",
                (channel_id,)
            )
            await self._conn.commit()

    async def get_gang_territories(self, gang_id: int) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT channel_id FROM territory_control WHERE gang_id=? AND locked=0",
                (gang_id,)
            )
            rows = await cur.fetchall()
        return [r[0] for r in rows]

    # ==================================================================
    # BASKINLAR
    # ==================================================================
    async def create_raid(self, attacker_gang: int, defender_gang: int,
                          channel_id: int, duration: int) -> int:
        now = int(time.time())
        async with self._lock:
            cur = await self._conn.execute(
                """INSERT INTO raids (attacker_gang, defender_gang, channel_id,
                                       status, start_time, end_time)
                   VALUES (?, ?, ?, 'ongoing', ?, ?)""",
                (attacker_gang, defender_gang, channel_id, now, now + duration)
            )
            await self._conn.commit()
            return cur.lastrowid

    async def get_active_raid(self, channel_id: int) -> Optional[dict]:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM raids WHERE channel_id=? AND status='ongoing' ORDER BY id DESC LIMIT 1",
                (channel_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    async def update_raid_status(self, raid_id: int, status: str, winner: int = None):
        async with self._lock:
            await self._conn.execute(
                "UPDATE raids SET status=?, winner_gang_id=? WHERE id=?",
                (status, winner, raid_id)
            )
            await self._conn.commit()

    async def get_all_active_raids(self) -> list:
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT * FROM raids WHERE status='ongoing'"
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]

    # ==================================================================
    # KARAKTER OLUM / PERMADEATH
    # ==================================================================
    async def mark_character_dead(self, user_id: int, reason: str = ""):
        """Karakteri olu olarak isaretle. Tombstone'a kaydeder.
        3 gun sonra permanently_delete_character cagrilir (tasks.py).
        """
        user = await self.get_user(user_id)
        if not user:
            return
        async with self._lock:
            now_iso = datetime.now(TZ_ISTANBUL).isoformat()
            await self._conn.execute(
                """INSERT OR REPLACE INTO tombstones
                   (user_id, isim, soyisim, yas, sehir, meslek, death_date, death_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, user.get('isim'), user.get('soyisim'), user.get('yas'),
                 user.get('sehir'), user.get('meslek'), now_iso, reason)
            )
            await self._conn.execute(
                "UPDATE users SET is_dead=1, death_date=?, can=0 WHERE user_id=?",
                (now_iso, user_id)
            )
            await self._conn.commit()

    async def admin_reset_character(self, user_id: int) -> bool:
        """Admin komutuyla karakter sifirlama. Iki asamali onay sisteminden sonra cagrilir."""
        async with self._lock:
            await self._conn.execute("DELETE FROM inventory WHERE user_id=?", (user_id,))
            # FIX: Cete uyeligi de silinmeli (onay ekraninda vaat ediliyordu).
            await self._conn.execute("DELETE FROM gang_members WHERE user_id=?", (user_id,))
            await self._conn.execute(
                """UPDATE users SET
                    isim=NULL, soyisim=NULL, yas=NULL, sehir=NULL, meslek=NULL,
                    can=100, acluk=100, susuzluk=100, para=100,
                    is_dead=0, death_date=NULL,
                    enfeksiyon_suresi=0, enfeksiyon_baslangic=0, enfeksiyon_seviye=0,
                    slot_seviye=0, gozlemci=0
                WHERE user_id=?""",
                (user_id,)
            )
            await self._conn.commit()
        # FIX: add_action_log kendi icinde lock aliyor; lock icinden
        # cagirilinca asyncio.Lock reentrant olmadigi icin butun bot
        # DB islemleri sonsuza kadar bekliyordu (deadlock).
        await self.add_action_log('admin', None, user_id, 'karakter_sifirla', {})
        return True

    async def permanently_delete_character(self, user_id: int):
        """3 gunluk karantina sonrasi karakteri gercekten sil.
        users tablosunda kayit kalir ama tum RP verisi sifirlanir, gozlemciye cevrilir.
        """
        async with self._lock:
            await self._conn.execute("DELETE FROM inventory WHERE user_id=?", (user_id,))
            await self._conn.execute("DELETE FROM gang_members WHERE user_id=?", (user_id,))
            await self._conn.execute(
                """UPDATE users SET
                    isim=NULL, soyisim=NULL, yas=NULL, sehir=NULL, meslek=NULL,
                    can=100, acluk=100, susuzluk=100, para=0,
                    is_dead=0, death_date=NULL,
                    enfeksiyon_suresi=0, enfeksiyon_baslangic=0, enfeksiyon_seviye=0,
                    slot_seviye=0, gozlemci=1
                WHERE user_id=?""",
                (user_id,)
            )
            await self._conn.commit()

    async def revive_character(self, user_id: int) -> bool:
        """Itiraz sonrasi karakteri geri getir (admin)."""
        async with self._lock:
            cur = await self._conn.execute(
                "SELECT isim, soyisim, yas, sehir, meslek FROM tombstones WHERE user_id=?",
                (user_id,)
            )
            row = await cur.fetchone()
            if not row:
                return False
            await self._conn.execute(
                """UPDATE users SET isim=?, soyisim=?, yas=?, sehir=?, meslek=?,
                    is_dead=0, death_date=NULL, can=50, acluk=50, susuzluk=50, para=50,
                    enfeksiyon_suresi=0, enfeksiyon_baslangic=0, enfeksiyon_seviye=0
                WHERE user_id=?""",
                (*row[:5], user_id)
            )
            await self._conn.execute("DELETE FROM tombstones WHERE user_id=?", (user_id,))
            await self._conn.commit()
            return True

    async def get_dead_characters(self, older_than_days: int = None) -> list:
        """Olu karakterleri getir."""
        if older_than_days is not None:
            threshold = int(time.time()) - (older_than_days * 86400)
        else:
            threshold = 0
        async with self._lock:
            cur = await self._conn.execute(
                """SELECT user_id, isim, soyisim, yas, sehir, meslek, death_date
                   FROM users WHERE is_dead=1"""
            )
            rows = await cur.fetchall()
        results = []
        for r in rows:
            if older_than_days is not None:
                try:
                    dt = datetime.fromisoformat(r[6]).timestamp()
                    if dt > threshold:
                        continue
                except Exception:
                    continue
            results.append({
                "user_id": r[0], "isim": r[1], "soyisim": r[2],
                "yas": r[3], "sehir": r[4], "meslek": r[5],
                "death_date": r[6]
            })
        return results


# ==================================================================
# GLOBAL DATABASE INSTANCE
# ==================================================================
db = Database()
