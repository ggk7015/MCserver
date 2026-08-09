# DCBot 本機啟動
# 第一次使用請先複製 .env.example 為 .env 並填入 DISCORD_TOKEN / SFTP_PASS

@echo off
cd /d %~dp0
if not exist .env (
    echo [ERROR] 找不到 .env 檔，請先複製 .env.example 並改名為 .env
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
python bot.py
pause
