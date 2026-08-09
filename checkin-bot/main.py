import datetime
import json
import os
import sqlite3

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

try:
    import paramiko
except ImportError:
    paramiko = None

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.getenv("DISCORD_TOKEN")
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "900"))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
LOCAL_DB = os.path.join(BASE_DIR, "checkin.db")

SFTP_HOST = os.getenv("SFTP_HOST", "")
SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
SFTP_USER = os.getenv("SFTP_USER", "")
SFTP_PASS = os.getenv("SFTP_PASS", "")
SERVER_SIGNIN_DB = os.getenv("SERVER_SIGNIN_DB", "/plugins/LiteSignIn/Database.db")
SERVER_ACCOUNTS_AOF = os.getenv("SERVER_ACCOUNTS_AOF", "/plugins/DiscordSRV/accounts.aof")
SERVER_USERCACHE = os.getenv("SERVER_USERCACHE", "/usercache.json")

conn = sqlite3.connect(LOCAL_DB)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    total INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    last_checkin TEXT
)
""")
conn.commit()


def get_user(user_id: int):
    cur.execute(
        "SELECT total, streak, points, last_checkin FROM users WHERE user_id=?", (user_id,)
    )
    return cur.fetchone()


def sync_all():
    if paramiko is None:
        return False
    os.makedirs(CACHE_DIR, exist_ok=True)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=SFTP_HOST,
        port=SFTP_PORT,
        username=SFTP_USER,
        password=SFTP_PASS,
        timeout=30,
    )
    try:
        sftp = client.open_sftp()
        remote_files = [
            (SERVER_SIGNIN_DB, os.path.join(CACHE_DIR, "Database.db")),
            (SERVER_ACCOUNTS_AOF, os.path.join(CACHE_DIR, "accounts.aof")),
            (SERVER_USERCACHE, os.path.join(CACHE_DIR, "usercache.json")),
        ]
        for remote, local in remote_files:
            try:
                sftp.get(remote, local)
            except FileNotFoundError:
                pass
        sftp.close()
    finally:
        client.close()
    return True


def read_linked_accounts():
    path = os.path.join(CACHE_DIR, "accounts.aof")
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


def uuid_to_name(uuid):
    uuid = uuid.lower()
    path = os.path.join(CACHE_DIR, "usercache.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for entry in data:
                if entry.get("uuid", "").lower() == uuid:
                    return entry.get("name")
        except (json.JSONDecodeError, OSError):
            pass
    db_path = os.path.join(CACHE_DIR, "Database.db")
    if os.path.exists(db_path):
        try:
            db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = db.execute(
                "SELECT Name FROM playerdata WHERE UUID = ?", (uuid,)
            ).fetchone()
            db.close()
            if row:
                return row[0]
        except sqlite3.Error:
            pass
    return None


def server_signin_dates(name):
    db_path = os.path.join(CACHE_DIR, "Database.db")
    if not os.path.exists(db_path):
        return set()
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = db.execute(
            "SELECT History FROM playerdata WHERE Name = ?", (name,)
        ).fetchone()
        db.close()
    except sqlite3.Error:
        return set()
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
                dates.add(
                    f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                )
            except ValueError:
                continue
    return dates


def resolve_player(discord_id):
    linked = read_linked_accounts()
    uuid = linked.get(discord_id)
    if not uuid:
        return None, None
    return uuid, uuid_to_name(uuid)


def bind_instructions():
    return (
        "你尚未綁定 Discord 與遊戲帳號。\n"
        "請依照以下步驟完成綁定：\n"
        "1. 進入伺服器\n"
        "2. 在遊戲內輸入 `/discord link`\n"
        "3. 依照指示將驗證碼以私訊傳送給機器人\n"
        "4. 綁定成功後，即可使用 `/checkin` 簽到"
    )


def reward_text(continuous, total, first, weekday, hour):
    lines = ["**每日簽到獎勵**", "- 鑽石 x1", "- 金錠 x3", "- 鐵錠 x6"]
    if continuous == 3:
        lines.append("**連簽 3 天：獎勵翻倍！**")
    if continuous == 7:
        lines.append("**連簽 7 天：額外獲得 超神鑽石劍 x1 + 金蘋果 x1**")
    if continuous > 0 and continuous % 3 == 0:
        lines.append(f"**週期連簽 {continuous} 天：額外獲得 金蘋果 x1**")
    if weekday == 6:
        lines.append("**今天是週日：額外獲得 金蘋果 x1**")
    if hour >= 22 or hour < 3:
        lines.append("**深夜簽到：獲得 牛奶 x1，請早點休息**")
    if first:
        lines.append("**你是今日第一個簽到的玩家，獎勵翻倍！**")
    if total == 100:
        lines.append("**累計簽到 100 天：獲得 10000 金幣（請至遊戲內領取）**")
    if total > 0 and total % 100 == 0:
        lines.append(f"**累計簽到 {total} 天：獲得 5000 金幣（請至遊戲內領取）**")
    return "\n".join(lines)


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


@tasks.loop(seconds=max(SYNC_INTERVAL, 60))
async def sync_loop():
    try:
        sync_all()
    except Exception:
        pass


@tree.command(name="checkin", description="每日簽到，每天只能簽到一次")
async def checkin(interaction: discord.Interaction):
    await interaction.response.defer()
    _, mc_name = resolve_player(interaction.user.id)
    if not mc_name:
        await interaction.followup.send(bind_instructions())
        return
    user_id = interaction.user.id
    today = datetime.date.today()
    row = get_user(user_id)

    server_dates = server_signin_dates(mc_name)
    server_today = today.isoformat() in server_dates

    if row is None:
        cur.execute(
            "INSERT INTO users (user_id, total, streak, points, last_checkin) VALUES (?, 1, 1, 1, ?)",
            (user_id, today.isoformat()),
        )
        conn.commit()
        total = 1
        streak = 1
        first = True
    else:
        total, streak, points, last = row
        if last == today.isoformat():
            msg = f"⚠️ {interaction.user.mention} 你今天已經簽到過了，明天再來！目前連續 {streak} 天，共 {points} 點"
            if server_today:
                msg += f"\n（遊戲名 `{mc_name}` 今天也已在伺服器內簽到）"
            await interaction.followup.send(msg)
            return
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        new_streak = streak + 1 if last == yesterday else 1
        total += 1
        points += 1
        cur.execute(
            "UPDATE users SET total=?, streak=?, points=?, last_checkin=? WHERE user_id=?",
            (total, new_streak, points, today.isoformat(), user_id),
        )
        conn.commit()
        streak = new_streak
        first = False

    merged = server_dates | {today.isoformat()}
    continuous = 0
    day = today
    while day.isoformat() in merged:
        continuous += 1
        day -= datetime.timedelta(days=1)
    now = datetime.datetime.now()
    reward = reward_text(
        continuous, len(merged), first, now.weekday(), now.hour
    )
    msg = (
        f"✅ {interaction.user.mention} 簽到成功！\n"
        f"綁定遊戲名：`{mc_name}`\n"
        f"今日：{today.isoformat()}\n"
        f"連續簽到：**{continuous} 天**\n"
        f"累計簽到：**{len(merged)} 天**\n\n"
        f"{reward}\n\n"
        f"物品獎勵將於伺服器遊戲內發放，請登入領取。"
    )
    await interaction.followup.send(msg)


@tree.command(name="profile", description="查看自己的簽到資料")
async def profile(interaction: discord.Interaction):
    row = get_user(interaction.user.id)
    _, mc_name = resolve_player(interaction.user.id)
    embed = discord.Embed(
        title=f"{interaction.user.display_name} 的簽到資料", color=0x00FF88
    )
    if row:
        total, streak, points, last = row
        embed.add_field(name="Discord 總簽到次數", value=f"{total} 次", inline=True)
        embed.add_field(name="Discord 連續天數", value=f"{streak} 天", inline=True)
        embed.add_field(name="累積點數", value=f"{points} 點", inline=True)
        embed.add_field(name="上次簽到", value=last, inline=False)
    else:
        embed.add_field(name="狀態", value="你還沒在 Discord 簽到過，先用 /checkin 簽到吧！", inline=False)
    if mc_name:
        server_dates = server_signin_dates(mc_name)
        embed.add_field(
            name="伺服器簽到（LiteSignIn）",
            value=f"遊戲名 `{mc_name}`，伺服器內累計 **{len(server_dates)} 天**",
            inline=False,
        )
    else:
        embed.add_field(
            name="伺服器簽到（LiteSignIn）",
            value="尚未綁定遊戲帳號，無法查詢",
            inline=False,
        )
    await interaction.response.send_message(embed=embed)


@tree.command(name="top", description="查看簽到排行榜")
async def top(interaction: discord.Interaction):
    cur.execute("SELECT user_id, streak, points FROM users ORDER BY streak DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows:
        await interaction.response.send_message("還沒有人簽到過。")
        return
    lines = []
    for i, (uid, streak, points) in enumerate(rows, 1):
        user = bot.get_user(uid)
        name = user.display_name if user else f"<@{uid}>"
        lines.append(f"**{i}.** {name} — 連續 {streak} 天，{points} 點")
    await interaction.response.send_message("🏆 **簽到排行榜**\n" + "\n".join(lines))


@tree.command(name="bind", description="查看綁定狀態")
async def bind(interaction: discord.Interaction):
    await interaction.response.defer()
    _, mc_name = resolve_player(interaction.user.id)
    if not mc_name:
        await interaction.followup.send(bind_instructions())
        return
    await interaction.followup.send(
        f"✅ 已綁定。你的 Discord 帳號對應遊戲名稱：`{mc_name}`"
    )


@bot.event
async def on_ready():
    await tree.sync()
    print(f"BOT 已上線：{bot.user}（ID: {bot.user.id}）")
    try:
        sync_all()
        print("伺服器資料同步完成。")
    except Exception as exc:
        print(f"首次同步失敗：{exc}")
    if not sync_loop.is_running():
        sync_loop.start()


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("請先設定 DISCORD_TOKEN")
    bot.run(TOKEN)
