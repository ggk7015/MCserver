# Discord 機器人建立教學（取得金鑰）

以下步驟將引導你在 Discord 開發者網站建立自己的機器人，並取得機器人金鑰與邀請連結。
網站介面為英文，括號內附中文說明方便對照。

## 一、建立應用程式

1. 開啟網頁 https://discord.com/developers/applications ，登入你的 Discord 帳號
2. 點擊右上角「New Application」（新增應用程式）
3. 輸入應用程式名稱（例如：`DCBot`），點擊「Create」（建立）

## 二、建立機器人並取得金鑰

1. 點擊左側選單「Bot」（機器人）
2. 點擊「Add Bot」（新增機器人）→ 跳出確認視窗後點擊「Yes, do it!」（是，執行）
3. 在「Token」（金鑰）欄位點擊「Reset Token」（重設金鑰）→ 再點擊「Copy」（複製）以複製金鑰
   - 金鑰格式大致為 `MTE3xxxxxxxxxxxxxxxxxxxxx.yyyy.zzzzzz`
   - 這把金鑰等同機器人的密碼，請勿告訴別人或公開
4. （建議）關閉「Public Bot」（公開機器人），避免被不認識的人加入其他伺服器
5. （建議）在「Privileged Gateway Intents」（特權閘道意圖）開啟「SERVER MEMBERS INTENT」（伺服器成員意圖）

## 三、邀請機器人加入你的 Discord 伺服器

1. 點擊左側選單「OAuth2」（授權）→「URL Generator」（網址產生器）
2. 在「Scopes」（範圍）勾選：`bot`（機器人）、`applications.commands`（斜線指令）
3. 在「Bot Permissions」（機器人權限）勾選：
   - 「Send Messages」（傳送訊息）
   - 「Embed Links」（嵌入連結）
   - 「Use Slash Commands」（使用斜線指令）
   - （如需查詢伺服器成員：「Read Members」（讀取成員））
4. 頁面下方會產生一段網址，將它貼到瀏覽器開啟 → 選擇你的伺服器 → 點「授權」

## 四、取得 Discord 伺服器代號

1. 開啟 Discord 主程式，點擊左下角「使用者設定」→「進階」（Advanced）→ 開啟「開發者模式」（Developer Mode）
2. 在你想要使用的伺服器名稱上按滑鼠右鍵 → 點「複製伺服器代號」（Copy Server ID）
3. 將代號填入 `.env` 檔案中的 `GUILD_IDS`（可填多個，用逗號分隔）

## 五、填入設定

編輯 `.env` 檔案（若無此檔，請先複製 `.env.example` 並改名為 `.env`）：

```
DISCORD_TOKEN=貼上你的機器人金鑰
GUILD_IDS=你的Discord伺服器代號
SFTP_HOST=tw-c-sftp.mcloudtw.com
SFTP_PORT=2022
SFTP_USER=zhaochenliu0330ppd.67f4055d
SFTP_PASS=貼上你的SFTP密碼
```

## 六、本機執行

執行 `start_local.bat`，看到 `Logged in as DCBot#1234` 即代表啟動成功。
之後即可在 Discord 使用 `/checkin`（簽到）、`/bind`（查看綁定）、`/signin-info`（查詢紀錄）、`/help`（說明）。
