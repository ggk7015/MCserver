# DCBot — Minecraft 伺服器 Discord 簽到機器人

基於伺服器原有 **LiteSignIn** 簽到系統建立的 Discord 簽到機器人。
玩家可在 Discord 上每日簽到；第一次使用需先綁定遊戲名稱（沿用 **DiscordSRV** 綁定機制）。

> **首次設定請先閱讀**：[Discord Bot 建立教學](./DISCORD_BOT_SETUP.md)（取得 Token 與伺服器 ID）
> **本機測試**：複製 `.env.example` 為 `.env` 填入 Token / SFTP 密碼，執行 `start_local.bat`

## 功能

- `/checkin` — 每日簽到（每日一次）
- `/signin-info` — 查詢簽到資訊（今日是否已簽、連續/累計天數、最近紀錄）
- `/bind` — 查看 Discord 綁定的遊戲名稱
- `/help` — 使用說明

## 綁定機制

沿用 DiscordSRV 綁定：

1. 進入伺服器，遊戲內輸入 `/discord link`
2. 依照指示將驗證碼以私訊傳送給機器人
3. 綁定完成後即可在 Discord 使用 `/checkin` 簽到

機器人會定期（預設 15 分鐘）透過 SFTP 唯讀下載伺服器端兩份資料：
- `plugins/LiteSignIn/Database.db` — 簽到紀錄（供比對是否今日已於遊戲內簽到、顯示簽到資訊）
- `plugins/DiscordSRV/accounts.aof` — Discord ↔ 遊戲帳號綁定表

> 機器人**只讀取**伺服器資料，**不會寫入**伺服器任何檔案。Discord 簽到紀錄儲存在機器人自己的 SQLite（`data/dcbot.db`）。

## 環境變數

| 變數 | 說明 | 必填 |
|---|---|---|
| `DISCORD_TOKEN` | Discord Bot Token | 是 |
| `GUILD_IDS` | 伺服器（Discord Guild）ID，逗號分隔；留空則註冊為全域指令 | 否 |
| `SFTP_HOST` | Minecraft 主機 SFTP 位址 | 是 |
| `SFTP_PORT` | SFTP 連接埠（mcloudtw 為 `2022`） | 否 |
| `SFTP_USER` | SFTP 帳號 | 是 |
| `SFTP_PASS` | SFTP 密碼 | 是 |
| `SYNC_INTERVAL` | 同步間隔（秒，預設 900） | 否 |

> `.env`（本機用）不會上傳；雲端部署請在平台上逐項設定環境變數。

## 本機執行

```bash
pip install -r requirements.txt
copy .env.example .env
# 編輯 .env 填入 DISCORD_TOKEN 與 SFTP_PASS
python bot.py
```

Windows 亦可直接執行 `start_local.bat`。

## Render 部署

1. 將本資料夾上傳到 GitHub 私有 repo
2. Render 新增 **Blueprint**，匯入該 repo（自動讀取 `render.yaml`）
3. 在 Render 專案中填寫 `DISCORD_TOKEN`、`SFTP_HOST`、`SFTP_USER`、`SFTP_PASS`（`sync: false` 的變數需手動輸入）
4. 部署完成後即上線

## Railway 部署

1. 將本資料夾上傳到 GitHub 私有 repo
2. Railway 建立新專案 → **Deploy from GitHub repo**
3. 於 **Variables** 加入上表環境變數
4. 部署後可於 Logs 確認 `Logged in as ...`

## 簽到獎勵（與 LiteSignIn 一致）

- 每日：鑽石 x1、金錠 x3、鐵錠 x6
- 連簽 3 天：獎勵翻倍
- 連簽 7 天：額外 超神鑽石劍 x1 + 金蘋果 x1
- 週期連簽（每 3 天）：金蘋果 x1
- 週日簽到：金蘋果 x1
- 深夜簽到（22:30 後）：牛奶 x1
- 當日首位簽到：獎勵翻倍
- 累計 100 天：10000 金幣；之後每滿 100 天：5000 金幣

物品獎勵請登入伺服器領取（由遊戲內系統發放）。
