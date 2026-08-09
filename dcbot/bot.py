import asyncio
import datetime
import os

import aiohttp
import discord
from discord.ext import commands, tasks

import config
import signin
import sync

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def _guilds():
    if config.GUILD_IDS:
        return [discord.Object(id=g) for g in config.GUILD_IDS]
    return None


@tasks.loop(seconds=max(config.SYNC_INTERVAL, 60))
async def sync_loop():
    try:
        sync.sync_all()
    except Exception:
        pass


async def run_health_server():
    port = int(os.environ.get("PORT", "0"))
    if not port:
        return

    async def health(request):
        return aiohttp.web.Response(text="ok")

    app = aiohttp.web.Application()
    app.router.add_get("/", health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Health server started on port {port}")


def _resolve_player(discord_id):
    linked = signin.read_linked_accounts()
    uuid = linked.get(discord_id)
    if not uuid:
        return None, None
    name = signin.uuid_to_name(uuid)
    return uuid, name


def _bind_instructions():
    return (
        "你尚未綁定 Discord 與遊戲帳號。\n"
        "請依照以下步驟完成綁定：\n"
        "1. 進入伺服器\n"
        "2. 在遊戲內輸入 `/discord link`\n"
        "3. 依照指示將驗證碼以私訊傳送給本機器人\n"
        "4. 綁定成功後，即可使用 `/checkin` 簽到"
    )


@bot.tree.command(name="checkin", description="每日簽到")
async def checkin(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    _, name = _resolve_player(interaction.user.id)
    if not name:
        await interaction.followup.send(_bind_instructions(), ephemeral=True)
        return
    today = signin.do_checkin(interaction.user.id, name)
    if today is None:
        await interaction.followup.send(
            f"你（遊戲名 `{name}`）今天已經簽到過了！明天再來吧。", ephemeral=True
        )
        return
    dates = signin._all_dates(interaction.user.id, name)
    continuous = signin.calc_consecutive(dates)
    total = signin.calc_total(dates)
    first = signin.is_first_of_day()
    now = datetime.datetime.now()
    reward = signin.reward_text(
        continuous, total, first, now.weekday(), now.hour
    )
    msg = (
        f"✅ 簽到成功！\n"
        f"綁定遊戲名：`{name}`\n"
        f"今日：{today}\n"
        f"連續簽到：**{continuous} 天**\n"
        f"累計簽到：**{total} 天**\n\n"
        f"{reward}\n\n"
        f"物品獎勵將於伺服器遊戲內發放，請登入領取。"
    )
    await interaction.followup.send(msg, ephemeral=True)


@bot.tree.command(name="signin-info", description="查詢簽到資訊")
async def signin_info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    _, name = _resolve_player(interaction.user.id)
    if not name:
        await interaction.followup.send(_bind_instructions(), ephemeral=True)
        return
    dates = signin._all_dates(interaction.user.id, name)
    continuous = signin.calc_consecutive(dates)
    total = signin.calc_total(dates)
    today = signin.today_str()
    checked = today in dates
    recent = sorted(dates)[-10:] if dates else []
    lines = [
        f"綁定遊戲名：`{name}`",
        f"今日（{today}）是否已簽到：{'是' if checked else '否'}",
        f"連續簽到：**{continuous} 天**",
        f"累計簽到：**{total} 天**",
    ]
    if recent:
        lines.append("最近簽到日期：")
        lines.extend(f"- {d}" for d in reversed(recent))
    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="bind", description="查詢綁定狀態")
async def bind(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    _, name = _resolve_player(interaction.user.id)
    if not name:
        await interaction.followup.send(_bind_instructions(), ephemeral=True)
        return
    await interaction.followup.send(
        f"✅ 已綁定。你的 Discord 帳號對應遊戲名稱：`{name}`",
        ephemeral=True,
    )


@bot.tree.command(name="help", description="使用說明")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    text = (
        "**簽到機器人使用說明**\n\n"
        "1. 第一次使用請先綁定：遊戲內輸入 `/discord link`，"
        "取得驗證碼後私訊本機器人即可完成綁定。\n"
        "2. 綁定後每天可使用 `/checkin` 簽到一次。\n"
        "3. `/signin-info` 查詢你的簽到紀錄。\n"
        "4. `/bind` 查看綁定狀態。\n\n"
        "簽到獎勵與伺服器 LiteSignIn 系統一致："
        "每日鑽石 x1、金錠 x3、鐵錠 x6；"
        "連簽 3 天翻倍、7 天額外獎勵、週日與深夜有額外禮物。\n\n"
        "物品獎勵請至遊戲內領取。"
    )
    await interaction.followup.send(text, ephemeral=True)


@bot.event
async def on_ready():
    guilds = _guilds()
    if guilds:
        for g in guilds:
            await bot.tree.sync(guild=g)
    else:
        await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        sync.sync_all()
        print("Initial sync completed.")
    except Exception as exc:
        print(f"Initial sync failed: {exc}")
    if not sync_loop.is_running():
        sync_loop.start()
    await run_health_server()


def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN")
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
