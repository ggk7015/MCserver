import datetime
import json
import os
import sqlite3

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.getenv(
    "ARCHIVE_DIR",
    r"C:\Users\ggk\Desktop\archive-2026-08-10T065805+0800\DiscordSRV",
)
load_dotenv(os.path.join(ARCHIVE_DIR, ".env"))
TOKEN = os.getenv("DISCORD_TOKEN")
LOCAL_DB = os.path.join(ARCHIVE_DIR, "checkin.db")

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


def read_linked_accounts():
    path = os.path.join(ARCHIVE_DIR, "accounts.aof")
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
    path = os.path.join(ARCHIVE_DIR, "usercache.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            for entry in data:
                if entry.get("uuid", "").lower() == uuid:
                    return entry.get("name")
        except (json.JSONDecodeError, OSError):
            pass
    db_path = os.path.join(ARCHIVE_DIR, "Database.db")
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
    db_path = os.path.join(ARCHIVE_DIR, "Database.db")
    if not os.path.exists(db_path):
        return set()
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = db.execute(
            "SELECT History FROM playerdata WHERE Name = ?", (name,)
        ).fetchone()
        if not row:
            row = db.execute(
                "SELECT History FROM playerdata WHERE UUID = ?", (name,)
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
        "4. 綁定成功後，即可使用 `!簽到` 或 `/checkin` 簽到"
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


def checkin_message(user_id, mention):
    uuid, mc_name = resolve_player(user_id)
    if not uuid:
        return bind_instructions()
    display = mc_name if mc_name else f"UUID {uuid[:8]}"
    today = datetime.date.today()
    row = get_user(user_id)
    server_dates = server_signin_dates(display)
    server_today = today.isoformat() in server_dates

    if row is None:
        cur.execute(
            "INSERT INTO users (user_id, total, streak, points, last_checkin) VALUES (?, 1, 1, 1, ?)",
            (user_id, today.isoformat()),
        )
        conn.commit()
        total, streak, first = 1, 1, True
    else:
        total, streak, points, last = row
        if last == today.isoformat():
            msg = f"⚠️ {mention} 你今天已經簽到過了，明天再來！目前連續 {streak} 天，共 {points} 點"
            if server_today:
                msg += f"\n（遊戲名 `{display}` 今天也已在伺服器內簽到）"
            return msg
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
    reward = reward_text(continuous, len(merged), first, now.weekday(), now.hour)
    return (
        f"✅ {mention} 簽到成功！\n"
        f"綁定遊戲名：`{display}`\n"
        f"今日：{today.isoformat()}\n"
        f"連續簽到：**{continuous} 天**\n"
        f"累計簽到：**{len(merged)} 天**\n\n"
        f"{reward}\n\n"
        f"物品獎勵將於伺服器遊戲內發放，請登入領取。"
    )


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
tree = bot.tree


@bot.command(name="簽到", aliases=["checkin"])
async def cmd_checkin(ctx: commands.Context):
    await ctx.send(checkin_message(ctx.author.id, ctx.author.mention))


@bot.command(name="資料", aliases=["profile"])
async def cmd_profile(ctx: commands.Context):
    row = get_user(ctx.author.id)
    uuid, mc_name = resolve_player(ctx.author.id)
    lines = [f"**{ctx.author.display_name} 的簽到資料**"]
    if row:
        total, streak, points, last = row
        lines.append(f"Discord 總簽到：{total} 次")
        lines.append(f"Discord 連續：{streak} 天")
        lines.append(f"累積點數：{points} 點")
        lines.append(f"上次簽到：{last}")
    else:
        lines.append("你還沒在 Discord 簽到過，先用 `!簽到` 簽到吧！")
    if uuid:
        display = mc_name if mc_name else f"UUID {uuid[:8]}"
        server_dates = server_signin_dates(display)
        lines.append(f"伺服器簽到（LiteSignIn）：`{display}`，伺服器內累計 {len(server_dates)} 天")
    else:
        lines.append("伺服器簽到（LiteSignIn）：尚未綁定遊戲帳號，無法查詢")
    await ctx.send("\n".join(lines))


@bot.command(name="排行", aliases=["top"])
async def cmd_top(ctx: commands.Context):
    cur.execute("SELECT user_id, streak, points FROM users ORDER BY streak DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows:
        await ctx.send("還沒有人簽到過。")
        return
    lines = ["🏆 **簽到排行榜**"]
    for i, (uid, streak, points) in enumerate(rows, 1):
        user = bot.get_user(uid)
        name = user.display_name if user else f"<@{uid}>"
        lines.append(f"**{i}.** {name} — 連續 {streak} 天，{points} 點")
    await ctx.send("\n".join(lines))


@bot.command(name="綁定", aliases=["bind"])
async def cmd_bind(ctx: commands.Context):
    uuid, mc_name = resolve_player(ctx.author.id)
    if not uuid:
        await ctx.send(bind_instructions())
        return
    display = mc_name if mc_name else f"UUID {uuid[:8]}"
    await ctx.send(f"✅ 已綁定。你的 Discord 帳號對應：`{display}`")


@tree.command(name="checkin", description="每日簽到，每天只能簽到一次")
async def checkin(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send(
        checkin_message(interaction.user.id, interaction.user.mention)
    )


@tree.command(name="profile", description="查看自己的簽到資料")
async def profile(interaction: discord.Interaction):
    row = get_user(interaction.user.id)
    uuid, mc_name = resolve_player(interaction.user.id)
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
    if uuid:
        display = mc_name if mc_name else f"UUID {uuid[:8]}"
        server_dates = server_signin_dates(display)
        embed.add_field(
            name="伺服器簽到（LiteSignIn）",
            value=f"`{display}`，伺服器內累計 **{len(server_dates)} 天**",
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
    uuid, mc_name = resolve_player(interaction.user.id)
    if not uuid:
        await interaction.followup.send(bind_instructions())
        return
    display = mc_name if mc_name else f"UUID {uuid[:8]}"
    await interaction.followup.send(f"✅ 已綁定。你的 Discord 帳號對應：`{display}`")


@bot.event
async def on_ready():
    await tree.sync()
    print(f"BOT 已上線：{bot.user}（ID: {bot.user.id}）")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("請先設定 DISCORD_TOKEN")
    bot.run(TOKEN)
