import datetime
import json
import os
import sqlite3

import config


def _connect_server_db():
    path = os.path.join(config.CACHE_DIR, "Database.db")
    if not os.path.exists(path):
        return None
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def read_linked_accounts():
    path = os.path.join(config.CACHE_DIR, "accounts.aof")
    if not os.path.exists(path):
        return {}
    linked = {}
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    linked[int(parts[0])] = parts[1]
                except ValueError:
                    continue
    return linked


def _usercache_names():
    path = os.path.join(config.CACHE_DIR, "usercache.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return {entry.get("uuid", "").lower(): entry.get("name") for entry in data}
    except (json.JSONDecodeError, OSError):
        return {}


def uuid_to_name(uuid):
    uuid = uuid.lower()
    names = _usercache_names()
    if uuid in names and names[uuid]:
        return names[uuid]
    conn = _connect_server_db()
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT Name FROM playerdata WHERE UUID = ?", (uuid,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def server_signin_dates(name):
    conn = _connect_server_db()
    if conn is None:
        return set()
    try:
        row = conn.execute(
            "SELECT History FROM playerdata WHERE Name = ?", (name,)
        ).fetchone()
        if not row or not row[0]:
            return set()
        dates = set()
        for entry in row[0].split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split("-")
            if len(parts) >= 3:
                try:
                    dates.add(f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}")
                except ValueError:
                    continue
        return dates
    finally:
        conn.close()


def _local_conn():
    os.makedirs(os.path.dirname(config.LOCAL_DB), exist_ok=True)
    conn = sqlite3.connect(config.LOCAL_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS checkins("
        "discord_id INTEGER NOT NULL,"
        "mc_name TEXT NOT NULL,"
        "date TEXT NOT NULL,"
        "PRIMARY KEY(discord_id, date))"
    )
    return conn


def local_signin_dates(discord_id):
    conn = _local_conn()
    try:
        rows = conn.execute(
            "SELECT date FROM checkins WHERE discord_id = ?", (discord_id,)
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def _all_dates(discord_id, mc_name):
    return server_signin_dates(mc_name) | local_signin_dates(discord_id)


def today_str():
    return datetime.date.today().isoformat()


def calc_consecutive(dates):
    today = datetime.date.today()
    count = 0
    day = today
    while day.isoformat() in dates:
        count += 1
        day -= datetime.timedelta(days=1)
    return count


def calc_total(dates):
    return len(dates)


def already_signed_in(discord_id, mc_name):
    return today_str() in _all_dates(discord_id, mc_name)


def do_checkin(discord_id, mc_name):
    today = today_str()
    if already_signed_in(discord_id, mc_name):
        conn = _local_conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO checkins(discord_id, mc_name, date) VALUES (?,?,?)",
                (discord_id, mc_name, today),
            )
            conn.commit()
        finally:
            conn.close()
        return None
    conn = _local_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO checkins(discord_id, mc_name, date) VALUES (?,?,?)",
            (discord_id, mc_name, today),
        )
        conn.commit()
    finally:
        conn.close()
    return today


def is_first_of_day():
    conn = _local_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE date = ?", (today_str(),)
        ).fetchone()
        return row[0] == 1
    finally:
        conn.close()


def reward_text(continuous, total, first, weekday, hour):
    lines = []
    lines.append("**每日簽到獎勵**")
    lines.append("- 鑽石 x1")
    lines.append("- 金錠 x3")
    lines.append("- 鐵錠 x6")
    if continuous == 3:
        lines.append("**連簽 3 天：獎勵翻倍！**")
    if continuous == 7:
        lines.append("**連簽 7 天：額外獲得 超神鑽石劍 x1 + 金蘋果 x1**")
    if continuous % 3 == 0 and continuous > 0:
        lines.append(f"**週期連簽 {continuous} 天：額外獲得 金蘋果 x1**")
    if weekday == 6:
        lines.append("**今天是週日：額外獲得 金蘋果 x1**")
    if hour >= 22 or hour < 3:
        lines.append("**深夜簽到：獲得 牛奶 x1，請早點休息**")
    if first:
        lines.append("**你是今日第一個簽到的玩家，獎勵翻倍！**")
    if total == 100:
        lines.append("**累計簽到 100 天：獲得 10000 金幣（請至遊戲內領取）**")
    if total % 100 == 0 and total > 0:
        lines.append(f"**累計簽到 {total} 天：獲得 5000 金幣（請至遊戲內領取）**")
    return "\n".join(lines)
